"""
report_generator.py — xhtml2pdf-safe HTML report generator.

xhtml2pdf (ReportLab) known limitations:
  - NO flexbox / grid
  - NO CSS variables
  - Nested tables with width:100% inside padded containers = negative availWidth crash
  - Percentage widths in nested table cells are unreliable

Rules followed here to avoid all crashes:
  - All widths on outer tables are FIXED (pt), never percentage
  - Never nest a width:100% table inside a padded div (.section-box etc.)
  - Use <br/> for spacing instead of margins where possible
  - Avoid border-radius (partly supported but safe to include)
  - No emoji in critical layout paths (they can cause encode errors)
"""
from datetime import datetime
from typing import Dict, List, Any


# ── A4 body width in points: 595 - 2*56 (2cm margins) = 483pt
PAGE_W = 483   # usable body width in points


def _score_color(score: float) -> str:
    if score >= 80: return '#16a34a'
    if score >= 60: return '#d97706'
    return '#dc2626'


def _bar_color(pct: float) -> str:
    if pct >= 75: return '#16a34a'
    if pct >= 50: return '#d97706'
    return '#dc2626'


def _severity_color(sev: str) -> str:
    s = sev.lower()
    if s == 'high':            return '#dc2626'
    if s in ('moderate','medium'): return '#d97706'
    return '#2563eb'


def _pct(score: float, max_score: float) -> int:
    if max_score == 0: return 0
    return min(100, max(0, round(score / max_score * 100)))


def _css() -> str:
    return """<style>
@page { size: A4; margin: 2cm; }
body  { font-family: Helvetica, Arial, sans-serif; font-size: 11pt;
        color: #1e293b; margin: 0; padding: 0; line-height: 1.4; }
h2    { font-size: 13pt; color: #1e3a5f; margin: 18px 0 8px 0;
        border-bottom: 2px solid #e2e8f0; padding-bottom: 3px; }
h3    { font-size: 11pt; color: #374151; margin: 10px 0 5px 0; }
p     { margin: 0 0 6px 0; }
ul    { margin: 4px 0; padding-left: 16px; }
li    { margin-bottom: 2px; font-size: 9pt; }
table { border-collapse: collapse; }
td, th { vertical-align: top; }
</style>"""


def _header(title: str, subtitle: str = '', score_label: str = '',
             score_val: str = '', score_color: str = '#ffffff') -> str:
    """Dark navy header bar — uses fixed px widths, no nested %-tables."""
    score_block = ''
    if score_label and score_val:
        score_block = (
            f'<p style="font-size:9pt;color:#94a3b8;margin:0 0 2px 0;">{score_label}</p>'
            f'<p style="font-size:36pt;font-weight:bold;color:{score_color};'
            f'margin:0;line-height:1;">{score_val}</p>'
        )
    return f"""
<table width="{PAGE_W}" cellspacing="0" cellpadding="12"
       style="background:#1e3a5f; margin-bottom:16px;">
  <tr>
    {'<td width="110">' + score_block + '</td>' if score_block else ''}
    <td>
      <p style="font-size:15pt;font-weight:bold;color:#ffffff;margin:0;">{title}</p>
      {'<p style="font-size:9pt;color:#94a3b8;margin:2px 0 0 0;">' + subtitle + '</p>' if subtitle else ''}
    </td>
  </tr>
</table>"""


def _score_bar(label: str, score: float, max_score: float, sublabel: str = '') -> str:
    """Progress bar using solid background table cell — fixed widths only."""
    pct   = _pct(score, max_score)
    color = _bar_color(pct)
    # bar is 250pt wide total; filled portion in points
    bar_w = 250
    filled_w = max(2, round(pct / 100 * bar_w))
    empty_w  = bar_w - filled_w
    sub_html = (f'<br/><span style="font-size:8pt;color:#94a3b8;">{sublabel}</span>'
                if sublabel else '')
    return f"""
<table width="{PAGE_W}" cellspacing="0" cellpadding="0" style="margin-bottom:8px;">
  <tr>
    <td width="145" style="font-size:10pt;font-weight:bold;color:#334155;
        padding-right:8px;vertical-align:middle;">
      {label}{sub_html}
    </td>
    <td width="{bar_w}" style="vertical-align:middle;">
      <table cellspacing="0" cellpadding="0">
        <tr>
          <td width="{filled_w}" height="10"
              style="background:{color};height:10px;"></td>
          <td width="{empty_w}" height="10"
              style="background:#f1f5f9;height:10px;"></td>
        </tr>
      </table>
    </td>
    <td style="font-size:10pt;font-weight:bold;color:#1e293b;
        padding-left:8px;vertical-align:middle;">
      {score:.0f}/{max_score:.0f}
    </td>
  </tr>
</table>"""


def _info_box(text_html: str, color: str = '#2563eb',
              bg: str = '#eff6ff') -> str:
    """Simple bordered box — fixed width, no nested tables."""
    return f"""
<table width="{PAGE_W}" cellspacing="0" cellpadding="10"
       style="background:{bg};border-left:4px solid {color};margin-bottom:10px;">
  <tr><td style="font-size:10pt;">{text_html}</td></tr>
</table>"""


def _issue_block(issue: dict) -> str:
    sev   = issue.get('severity_level', 'low')
    color = _severity_color(sev)
    bg    = {'high': '#fef2f2', 'moderate': '#fffbeb',
             'medium': '#fffbeb'}.get(sev.lower(), '#eff6ff')
    title = issue.get('issue_title', '')
    expl  = issue.get('explanation', '')
    fix   = issue.get('how_to_fix', '')
    items = issue.get('action_items', []) or []
    items_html = ''.join(f'<li>{a}</li>' for a in items)

    fix_html  = f'<p style="font-size:9pt;color:#047857;margin:4px 0 0 0;"><b>Fix:</b> {fix}</p>' if fix else ''
    list_html = f'<ul>{items_html}</ul>' if items_html else ''

    return f"""
<table width="{PAGE_W}" cellspacing="0" cellpadding="10"
       style="background:{bg};border-left:4px solid {color};margin-bottom:10px;">
  <tr>
    <td>
      <table width="100%" cellspacing="0" cellpadding="0">
        <tr>
          <td style="font-size:10pt;font-weight:bold;color:{color};">{title}</td>
          <td width="60" style="text-align:right;font-size:8pt;font-weight:bold;
              color:{color};">[{sev.upper()}]</td>
        </tr>
      </table>
      <p style="font-size:9pt;margin:4px 0 0 0;">{expl}</p>
      {fix_html}
      {list_html}
    </td>
  </tr>
</table>"""


def _footer(report_label: str) -> str:
    return f"""
<table width="{PAGE_W}" cellspacing="0" cellpadding="6"
       style="margin-top:30px;border-top:1px solid #e2e8f0;">
  <tr>
    <td style="font-size:8pt;color:#94a3b8;">Generated by ATS Resume Scorer</td>
    <td style="text-align:right;font-size:8pt;color:#94a3b8;">{report_label}</td>
  </tr>
</table>"""


# ─── Report 1: Score Summary ──────────────────────────────────────────────────

def generate_summary_html(ctx: Dict) -> str:
    overall   = ctx['overall_score']
    score_col = _score_color(overall)
    cs        = ctx['component_scores']
    now_str   = datetime.now().strftime('%B %d, %Y at %I:%M %p')

    interp = ctx.get('interpretation', '')
    if not interp:
        if overall >= 80:   interp = "Great! Your resume should perform well with most ATS systems."
        elif overall >= 60: interp = "Good start. A few improvements will boost your score significantly."
        else:               interp = "Your resume needs work. Follow the recommendations below."

    # Strengths
    strengths_html = ''
    for s in ctx.get('strengths', []):
        strengths_html += _info_box(f'<b>+</b> {s}', '#16a34a', '#f0fdf4')
    if not strengths_html:
        strengths_html = _info_box('No major strengths detected yet — work through the recommendations.', '#94a3b8', '#f8fafc')

    # Critical issues
    issues_html = ''
    for issue in ctx.get('high_priority', []):
        issues_html += _issue_block(issue)
    if not issues_html:
        issues_html = _info_box('No critical issues found. Review recommendations for improvements.', '#16a34a', '#f0fdf4')

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>{_css()}</head><body>
{_header('ATS Resume Score Report', now_str,
         'OVERALL ATS SCORE', f'{overall:.0f}/100', score_col)}
<p style="font-size:10pt;font-style:italic;color:#475569;margin-bottom:14px;">{interp}</p>
<h2>Score Breakdown</h2>
{_score_bar('Formatting',      cs['formatting'],       20, 'Structure, headers, bullets')}
{_score_bar('Keywords & Skills', cs['keywords'],       25, 'Keyword density & relevance')}
{_score_bar('Content Quality', cs['content'],          25, 'Action verbs, metrics, achievements')}
{_score_bar('Skill Validation', cs['skill_validation'], 15, 'Skills backed by evidence')}
{_score_bar('ATS Compatibility', cs['ats_compatibility'], 15, 'Clean format, no parsing issues')}
<h2>Strengths</h2>
{strengths_html}
<h2>Critical Issues</h2>
{issues_html}
{_footer('Report 1 of 4 — Score Summary')}
</body></html>"""


# ─── Report 2: Detailed Feedback ─────────────────────────────────────────────

def generate_action_items_html(ctx: Dict) -> str:
    all_fb = ctx.get('all_feedback', [])
    vs     = ctx.get('validated_skills', [])
    uvs    = ctx.get('unvalidated_skills', [])
    total  = ctx.get('total_skills', 0)
    vc     = ctx.get('validated_count', 0)
    vpct   = ctx.get('validation_pct', 0.0)

    feedback_html = ''.join(_issue_block(fb) for fb in all_fb)
    if not feedback_html:
        feedback_html = _info_box('No detailed feedback available.', '#94a3b8', '#f8fafc')

    val_html  = ''.join(
        f'<li><b>{sv.get("skill", sv) if isinstance(sv, dict) else sv}</b>'
        + (f' — {", ".join(sv["projects"][:3])}' if isinstance(sv, dict) and sv.get("projects") else '')
        + '</li>'
        for sv in vs[:15]
    )
    uval_html = ''.join(f'<li>{s}</li>' for s in uvs[:15])

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>{_css()}</head><body>
{_header('Detailed Feedback & Action Items', 'Report 2 of 4')}
<h2>All Issues ({len(all_fb)} found)</h2>
{feedback_html}
<h2>Skill Validation</h2>
{_info_box(f'<b>{vc} / {total}</b> skills validated ({vpct:.0f}%)', '#2563eb', '#eff6ff')}
{'<h3>Validated Skills</h3><ul>' + val_html + '</ul>' if val_html else ''}
{'<h3>Unvalidated Skills</h3><ul>' + uval_html + '</ul>' if uval_html else ''}
{_footer('Report 2 of 4 — Detailed Feedback')}
</body></html>"""


# ─── Report 3: Quick Actions ──────────────────────────────────────────────────

def generate_quick_actions_html(ctx: Dict) -> str:
    high   = ctx.get('high_priority', [])
    medium = ctx.get('medium_priority', [])
    low    = ctx.get('low_priority', [])

    def _priority_table(items: List[dict], header_color: str) -> str:
        if not items:
            return '<p style="font-size:9pt;color:#64748b;">None</p>'
        rows = ''
        for i in items:
            rows += (
                f'<tr style="border-bottom:1px solid #e2e8f0;">'
                f'<td style="font-size:9pt;font-weight:bold;padding:5px 6px;width:200px;">'
                f'{i.get("issue_title","")}</td>'
                f'<td style="font-size:9pt;padding:5px 6px;">'
                f'{i.get("how_to_fix","")}</td></tr>'
            )
        return f"""
<table width="{PAGE_W}" cellspacing="0" cellpadding="0"
       style="margin-bottom:12px;border:1px solid #e2e8f0;">
  <tr>
    <th style="background:{header_color};color:#fff;font-size:9pt;
        padding:5px 6px;text-align:left;width:200px;">Issue</th>
    <th style="background:{header_color};color:#fff;font-size:9pt;
        padding:5px 6px;text-align:left;">Quick Fix</th>
  </tr>
  {rows}
</table>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>{_css()}</head><body>
{_header('Quick Actions Checklist', 'Report 3 of 4')}
<h2 style="color:#dc2626;">High Priority ({len(high)} issues)</h2>
{_priority_table(high, '#dc2626')}
<h2 style="color:#d97706;">Medium Priority ({len(medium)} issues)</h2>
{_priority_table(medium, '#d97706')}
<h2 style="color:#2563eb;">Low Priority ({len(low)} issues)</h2>
{_priority_table(low, '#2563eb')}
{_footer('Report 3 of 4 — Quick Actions')}
</body></html>"""


# ─── Report 4: JD Comparison ─────────────────────────────────────────────────

def generate_jd_comparison_html(ctx: Dict) -> str:
    jd = ctx.get('jd_analysis')

    if not jd:
        return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>{_css()}</head><body>
{_header('Job Description Comparison', 'Report 4 of 4')}
{_info_box('<b>No Job Description Provided</b><br/>Re-run the analysis with a job description to see keyword match and skills gap.', '#2563eb', '#eff6ff')}
{_footer('Report 4 of 4 — JD Comparison')}
</body></html>"""

    match_pct = float(jd.get('match_percentage', 0) or 0)
    sem_sim   = float(jd.get('semantic_similarity', 0) or 0)
    matched   = list(jd.get('matched_keywords', []) or [])[:20]
    missing   = list(jd.get('missing_keywords', []) or [])[:20]
    gap       = list(jd.get('skills_gap', []) or [])[:15]

    match_col    = _score_color(match_pct)
    matched_html = ''.join(f'<li>{k}</li>' for k in matched)
    missing_html = ''.join(f'<li>{k}</li>' for k in missing)
    gap_html     = ''.join(f'<li>{k}</li>' for k in gap)

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>{_css()}</head><body>
{_header('Job Description Comparison', f'Report 4 of 4 | Semantic similarity: {sem_sim:.1%}',
         'JD MATCH', f'{match_pct:.0f}%', match_col)}

<h2>Matched Keywords ({len(matched)})</h2>
{_info_box('<ul>' + matched_html + '</ul>' if matched_html else 'None matched yet.', '#16a34a', '#f0fdf4')}

<h2>Missing Keywords ({len(missing)})</h2>
{_info_box('<ul>' + missing_html + '</ul>' if missing_html else 'None missing — great match!', '#dc2626', '#fef2f2')}

{'<h2>Skills Gap</h2>' + _info_box('<ul>' + gap_html + '</ul>', '#d97706', '#fffbeb') if gap_html else ''}

{_footer('Report 4 of 4 — JD Comparison')}
</body></html>"""


# ─── Public entry point ───────────────────────────────────────────────────────

def generate_html_reports(analysis_data: Dict) -> Dict[str, str]:
    """Generate all 4 HTML report sections from an analysis result dict."""

    overall_score = float(
        analysis_data.get('ATS_score') or analysis_data.get('ats_score') or 0
    )

    cs_raw = analysis_data.get('component_scores') or {}
    if hasattr(cs_raw, 'model_dump'):  cs_raw = cs_raw.model_dump()
    elif hasattr(cs_raw, '__dict__'):  cs_raw = cs_raw.__dict__

    max_map = {'formatting': 20, 'keywords': 25, 'content': 25,
               'skill_validation': 15, 'ats_compatibility': 15}
    component_scores = {k: float(cs_raw.get(k) or 0) for k in max_map}
    component_pct    = {k: _pct(v, max_map[k]) for k, v in component_scores.items()}

    def _to_dict(item):
        if isinstance(item, dict): return item
        return item.model_dump() if hasattr(item, 'model_dump') else vars(item)

    raw_fb          = analysis_data.get('detailed_feedback') or []
    detailed_fb     = [_to_dict(fb) for fb in raw_fb]
    high_priority   = [fb for fb in detailed_fb if fb.get('severity_level','').lower() == 'high']
    medium_priority = [fb for fb in detailed_fb if fb.get('severity_level','').lower() in ('moderate','medium')]
    low_priority    = [fb for fb in detailed_fb if fb.get('severity_level','').lower() in ('low','info')]

    svd_raw = analysis_data.get('skill_validation_details') or {}
    if hasattr(svd_raw, 'model_dump'):  svd_raw = svd_raw.model_dump()
    elif hasattr(svd_raw, '__dict__'):  svd_raw = vars(svd_raw)

    jd_raw = analysis_data.get('jd_match_analysis') or analysis_data.get('jd_comparison')
    if jd_raw and hasattr(jd_raw, 'model_dump'):  jd_raw = jd_raw.model_dump()
    elif jd_raw and hasattr(jd_raw, '__dict__'):  jd_raw = vars(jd_raw)

    ctx = {
        'overall_score':      overall_score,
        'interpretation':     analysis_data.get('interpretation', ''),
        'component_scores':   component_scores,
        'component_pct':      component_pct,
        'strengths':          list(analysis_data.get('strengths') or []),
        'high_priority':      high_priority,
        'medium_priority':    medium_priority,
        'low_priority':       low_priority,
        'all_feedback':       detailed_fb,
        'validated_skills':   list(svd_raw.get('validated') or []),
        'unvalidated_skills': list(svd_raw.get('unvalidated') or []),
        'total_skills':       int(svd_raw.get('total') or 0),
        'validated_count':    int(svd_raw.get('validated_count') or 0),
        'validation_pct':     float(svd_raw.get('validation_pct') or 0),
        'jd_analysis':        jd_raw,
    }

    return {
        'summary':       generate_summary_html(ctx),
        'feedback':      generate_action_items_html(ctx),
        'quick_actions': generate_quick_actions_html(ctx),
        'jd_comparison': generate_jd_comparison_html(ctx),
    }