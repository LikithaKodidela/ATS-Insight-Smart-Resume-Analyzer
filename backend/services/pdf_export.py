import io
import re
import logging

logger = logging.getLogger('ats_resume_scorer')

# ── WeasyPrint (optional — requires GTK/Pango native libs, NOT available on bare Windows) ──
# WeasyPrint throws OSError (not ImportError) on Windows when GTK dlls are missing.
# We catch all exceptions here to prevent server crash on startup.
WEASYPRINT_AVAILABLE = False
try:
    from weasyprint import HTML as WeasyHTML
    # Do a quick smoke-test to confirm native libs are actually loaded
    WeasyHTML(string='<p>test</p>').render()
    WEASYPRINT_AVAILABLE = True
    logger.info("WeasyPrint is available and functional")
except Exception as _wp_err:
    logger.info(f"WeasyPrint unavailable ({type(_wp_err).__name__}: {_wp_err}) — will use xhtml2pdf")

# ── xhtml2pdf (pure Python, always works on Windows) ─────────────────────────
XHTML2PDF_AVAILABLE = False
try:
    from xhtml2pdf import pisa
    XHTML2PDF_AVAILABLE = True
    logger.info("xhtml2pdf is available")
except Exception as _xp_err:
    logger.warning(f"xhtml2pdf unavailable: {_xp_err}")


def _merge_html_docs(html_docs: dict) -> str:
    """Combine multiple HTML report strings into one document with page breaks."""
    parts = []
    for idx, (name, html_str) in enumerate(html_docs.items()):
        # Extract <body> content; if missing use the full string
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_str, re.DOTALL | re.IGNORECASE)
        content = body_match.group(1) if body_match else html_str

        if idx > 0:
            parts.append('<div style="page-break-before: always;"></div>')
        parts.append(f'<div class="section">{content}</div>')

    combined_body = '\n'.join(parts)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  @page {{ size: A4; margin: 1.5cm; }}
  body {{ font-family: Arial, Helvetica, sans-serif; font-size: 11pt; color: #1e293b; line-height: 1.5; }}
  h1 {{ font-size: 18pt; color: #1e3a5f; }}
  h2 {{ font-size: 14pt; color: #2563eb; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
  h3 {{ font-size: 12pt; color: #374151; }}
  .section {{ margin-bottom: 20px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
  th {{ background: #2563eb; color: white; padding: 6px 10px; text-align: left; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #e2e8f0; }}
  tr:nth-child(even) {{ background: #f8fafc; }}
  .score-badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: bold; }}
  .high {{ color: #dc2626; }} .medium {{ color: #d97706; }} .low {{ color: #16a34a; }}
  ul {{ padding-left: 18px; }} li {{ margin-bottom: 4px; }}
  .page-break {{ page-break-before: always; }}
</style>
</head>
<body>
{combined_body}
</body>
</html>"""


def _generate_with_xhtml2pdf(html_str: str) -> bytes:
    """Generate PDF bytes using xhtml2pdf (pure Python, Windows-compatible)."""
    output = io.BytesIO()
    result = pisa.CreatePDF(
        src=io.StringIO(html_str),
        dest=output,
        encoding='utf-8',
    )
    if result.err:
        raise RuntimeError(f"xhtml2pdf error code {result.err}")
    pdf = output.getvalue()
    if not pdf:
        raise RuntimeError("xhtml2pdf produced an empty PDF")
    return pdf


def _generate_with_weasyprint(html_docs: dict) -> bytes:
    """Generate PDF using WeasyPrint (requires GTK native libraries)."""
    documents = []
    for name, html_str in html_docs.items():
        doc = WeasyHTML(string=html_str).render()
        documents.append(doc)

    first_doc = documents[0]
    for other_doc in documents[1:]:
        for page in other_doc.pages:
            first_doc.pages.append(page)
    return first_doc.write_pdf()


def generate_combined_pdf(html_docs: dict) -> bytes:
    """
    Generate a combined PDF from multiple HTML report sections.

    Priority order:
      1. WeasyPrint  — best quality; needs GTK (not available on bare Windows)
      2. xhtml2pdf   — pure Python, works on all platforms including Windows
    """
    if not html_docs:
        raise ValueError("No HTML documents provided for PDF generation")

    # 1. WeasyPrint (only if confirmed available at startup)
    if WEASYPRINT_AVAILABLE:
        try:
            logger.info("Generating PDF with WeasyPrint")
            return _generate_with_weasyprint(html_docs)
        except Exception as exc:
            logger.warning(f"WeasyPrint failed ({exc}), falling back to xhtml2pdf")

    # 2. xhtml2pdf fallback
    if XHTML2PDF_AVAILABLE:
        logger.info("Generating PDF with xhtml2pdf")
        try:
            merged_html = _merge_html_docs(html_docs)
            return _generate_with_xhtml2pdf(merged_html)
        except Exception as exc:
            logger.error(f"xhtml2pdf failed: {exc}", exc_info=True)
            raise RuntimeError(f"PDF generation failed: {exc}") from exc

    raise ImportError(
        "No PDF backend is available. "
        "Run: pip install xhtml2pdf"
    )