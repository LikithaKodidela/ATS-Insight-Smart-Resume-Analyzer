"""
supabase_client.py — Frontend Supabase auth client.

Follows the architecture from the diagram:
  Step 1: Frontend calls Supabase Auth directly (sign_in / sign_up / OAuth).
           Supabase returns a JWT access_token.
           Frontend stores it in st.session_state.
  Step 2: Every FastAPI call includes:  Authorization: Bearer <access_token>
           Backend fetches Supabase JWKS, verifies the JWT, extracts user_id.

Config priority (highest → lowest):
  1. Environment variable  (SUPABASE_URL, SUPABASE_ANON_KEY, AUTH_REDIRECT_URL)
  2. st.secrets["supabase"] / st.secrets["google_oauth"]
     → add to .streamlit/secrets.toml for local dev,
       or set as environment variables on your deployment platform.
"""
import os
import logging
from pathlib import Path
from typing import Any, Dict

import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger('ats_resume_scorer')

# ── Load .env (local dev only; env vars take precedence in production) ────────
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parents[2]
    load_dotenv(_root / '.env')
    load_dotenv(_root / 'backend' / '.env', override=False)
except ImportError:
    pass


# ── Config helpers ─────────────────────────────────────────────────────────────

def _secret(key: str, section: str = 'supabase') -> str:
    """Reads from env var first, then st.secrets[section][key]."""
    val = os.getenv(key, '').strip()
    if val:
        return val
    try:
        return st.secrets[section][key]
    except (KeyError, FileNotFoundError, AttributeError):
        return ''


SUPABASE_URL     = _secret('SUPABASE_URL')
SUPABASE_ANON_KEY = _secret('SUPABASE_ANON_KEY')

# Redirect URL after Google OAuth — must match exactly what is registered in
# Supabase Dashboard → Authentication → URL Configuration → Redirect URLs.
OAUTH_REDIRECT_URL = (
    os.getenv('AUTH_REDIRECT_URL', '').strip()
    or _secret('redirect_uri', 'google_oauth')
    or 'http://localhost:8501'
)


def _missing_config() -> str | None:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return (
            'Supabase is not configured. '
            'Set SUPABASE_URL and SUPABASE_ANON_KEY as environment variables '
            'or in .streamlit/secrets.toml under [supabase].'
        )
    return None


# ── Supabase client (cached singleton) ────────────────────────────────────────

@st.cache_resource
def get_client() -> Client | None:
    """
    Cached singleton Supabase client.
    Uses the public anon key — safe to use in the frontend.
    The service_role key is NEVER used here (backend-only).
    """
    if _missing_config():
        return None
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _session_dict(session, user) -> Dict[str, Any]:
    return {
        'access_token':  session.access_token,
        'refresh_token': session.refresh_token,
        'user_id':       user.id,
        'email':         user.email,
    }


def _humanize(exc: Exception) -> str:
    """Turn raw Supabase/network exceptions into user-friendly messages."""
    msg = str(exc)
    m   = msg.lower()
    if 'invalid login' in m or 'invalid credentials' in m or 'invalid_grant' in m:
        return 'Wrong email or password'
    if 'email not confirmed' in m:
        return 'Email not confirmed — please check your inbox'
    if 'user already registered' in m or 'already been registered' in m or 'already exists' in m:
        return 'An account with this email already exists — try signing in'
    if 'password should be at least' in m or 'password is too short' in m:
        return 'Password too short (minimum 6 characters)'
    if 'signup' in m and 'disabled' in m:
        return 'New sign-ups are currently disabled on this project'
    if 'email rate limit' in m or 'rate limit' in m:
        return 'Too many requests — please wait a minute and try again'
    if 'network' in m or 'connection' in m or 'timeout' in m:
        return 'Network error — check your connection and try again'
    return msg


def _check_client() -> Client | str:
    """Returns the client, or an error string if not available."""
    err = _missing_config()
    if err:
        return err
    client = get_client()
    if client is None:
        return 'Supabase client could not be initialized'
    return client


# ── Auth functions — all call Supabase directly (matching the flow diagram) ───

def sign_in_with_password(email: str, password: str) -> Dict[str, Any]:
    """
    Step 1 of the auth flow (diagram):
      Frontend → sign_in_with_password() → Supabase Auth → JWT access_token
    """
    if not email or not email.strip():
        return {'error': 'Please enter your email address'}
    if not password:
        return {'error': 'Please enter your password'}

    client = _check_client()
    if isinstance(client, str):
        return {'error': client}

    try:
        resp = client.auth.sign_in_with_password(
            {'email': email.strip(), 'password': password}
        )
        if not resp.session or not resp.user:
            return {'error': 'Sign-in failed — no session returned'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'sign_in_with_password failed: {exc}')
        return {'error': _humanize(exc)}


def sign_up_with_password(email: str, password: str) -> Dict[str, Any]:
    """
    Sign up directly with Supabase Auth.

    IMPORTANT: Email confirmation must be DISABLED in your Supabase project for
    users to sign in immediately. Go to:
      Supabase Dashboard → Authentication → Providers → Email
      → uncheck "Confirm email"  → Save

    Returns either:
      - session dict with access_token (signed in immediately)
      - {'pending_confirmation': True} if email confirmation is still on
      - {'error': '...'} on failure
    """
    if not email or not email.strip():
        return {'error': 'Please enter your email address'}
    if not password:
        return {'error': 'Please enter your password'}
    if len(password) < 6:
        return {'error': 'Password must be at least 6 characters'}

    client = _check_client()
    if isinstance(client, str):
        return {'error': client}

    try:
        resp = client.auth.sign_up({'email': email.strip(), 'password': password})

        # If Supabase returned a session, the user is logged in immediately
        # (email confirmation is OFF — the correct setting for this app).
        if resp.session and resp.user:
            logger.info(f'sign_up succeeded (auto-confirmed): {email}')
            return _session_dict(resp.session, resp.user)

        # User was created but email confirmation is still required.
        if resp.user:
            logger.info(f'sign_up created account (confirmation pending): {email}')
            return {'pending_confirmation': True, 'email': email.strip()}

        return {'error': 'Sign-up failed — please try again'}

    except Exception as exc:
        logger.warning(f'sign_up failed: {exc}')
        return {'error': _humanize(exc)}


def google_oauth_url() -> Dict[str, Any]:
    """
    Starts the Google OAuth PKCE flow.
    Returns the redirect URL the user should be sent to.
    After Google redirects back, call exchange_code_for_session().
    """
    client = _check_client()
    if isinstance(client, str):
        return {'error': client}

    try:
        resp = client.auth.sign_in_with_oauth({
            'provider': 'google',
            'options': {'redirect_to': OAUTH_REDIRECT_URL},
        })
        return {'url': resp.url}
    except Exception as exc:
        logger.warning(f'google_oauth_url failed: {exc}')
        return {'error': _humanize(exc)}


def exchange_code_for_session(auth_code: str) -> Dict[str, Any]:
    """
    Exchanges the ?code= query param (from Google redirect) for a JWT session.
    Called once at the top of streamlit_app.py when ?code= is in the URL.
    """
    client = _check_client()
    if isinstance(client, str):
        return {'error': client}

    try:
        # Retrieve PKCE code verifier from the client's internal storage
        storage_key   = f'{client.auth._storage_key}-code-verifier'
        code_verifier = client.auth._storage.get_item(storage_key) or ''

        resp = client.auth.exchange_code_for_session({
            'auth_code':     auth_code,
            'code_verifier': code_verifier,
            'redirect_to':   OAUTH_REDIRECT_URL,
        })
        if not resp.session or not resp.user:
            return {'error': 'Google sign-in returned no session — please try again'}
        return _session_dict(resp.session, resp.user)
    except Exception as exc:
        logger.warning(f'exchange_code_for_session failed: {exc}')
        return {'error': _humanize(exc)}


def sign_out() -> None:
    """Sign out from Supabase (invalidates the JWT on the server side)."""
    client = _check_client()
    if isinstance(client, str):
        return
    try:
        client.auth.sign_out()
    except Exception as exc:
        logger.warning(f'sign_out failed: {exc}')