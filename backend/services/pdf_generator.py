"""
pdf_generator.py — ReportLab-based PDF generator for ATS Resume reports.

Uses ReportLab Platypus (flowable layout engine) directly — no HTML conversion,
no WeasyPrint/xhtml2pdf — 100% pure Python, no native dependencies.
"""
import io
import logging
from datetime import datetime
from typing import Dict, List, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
# 1 pt = 1 unit in ReportLab coordinate system
pt = 1.0
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import HRFlowable

logger = logging.getLogger('ats_resume_scorer')

# ── Colour palette ────────────────────────────────────────────────────────────
NAVY   = colors.HexColor('#1e3a5f')
BLUE   = colors.HexColor('#2563eb')
GREEN  = colors.HexColor('#16a34a')
AMBER  = colors.HexColor('#d97706')
RED    = colors.HexColor('#dc2626')
SLATE  = colors.HexColor('#64748b')
LIGHT  = colors.HexColor('#f8fafc')
WHITE  = colors.white
BLACK  = colors.HexColor('#1e293b')

# ── Page geometry ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4        # 595.27 × 841.89 pt
MARGIN = 1.8 * cm
BODY_W = PAGE_W - 2 * MARGIN   # ≈ 457 pt


def _score_color(score: float):
    if score >= 80: return GREEN
    if score >= 60: return AMBER
    return RED


def _severity_color(sev: str):
    s = sev.lower()
    if s == 'high':              return RED
    if s in ('moderate','medium'): return AMBER
    return BLUE


def _styles():
    base = getSampleStyleSheet()
    defs = {
        'Title': ParagraphStyle('Title',   fontName='Helvetica-Bold', fontSize=20, textColor=WHITE,   leading=24),
        'Sub':   ParagraphStyle('Sub',     fontName='Helvetica',      fontSize=9,  textColor=colors.HexColor('#94a3b8'), leading=12),
        'H2':    ParagraphStyle('H2',      fontName='Helvetica-Bold', fontSize=13, textColor=NAVY,    leading=16, spaceBefore=14, spaceAfter=4),
        'H3':    ParagraphStyle('H3',      fontName='Helvetica-Bold', fontSize=11, textColor=BLACK,   leading=14, spaceBefore=8,  spaceAfter=2),
        'Body':  ParagraphStyle('Body',    fontName='Helvetica',      fontSize=10, textColor=BLACK,   leading=14, spaceAfter=4),
        'Small': ParagraphStyle('Small',   fontName='Helvetica',      fontSize=8,  textColor=SLATE,   leading=11),
        'Bold':  ParagraphStyle('Bold',    fontName='Helvetica-Bold', fontSize=10, textColor=BLACK,   leading=14),
        'Score': ParagraphStyle('Score',   fontName='Helvetica-Bold', fontSize=38, textColor=WHITE,   leading=42),
        'ScLbl': ParagraphStyle('ScLbl',   fontName='Helvetica',      fontSize=9,  textColor=colors.HexColor('#94a3b8'), leading=11),
        'Footer':ParagraphStyle('Footer',  fontName='Helvetica',      fontSize=8,  textColor=SLATE,   leading=10),
    }
    return defs


def _header_table(title: str, subtitle: str = '',
                  score_label: str = '', score_val: str = '',
                  score_color=None) -> Table:
    """Dark navy header bar with optional score on left."""
    st = _styles()
    if score_color is None:
        score_color = WHITE

    title_cell = [
        Paragraph(title,    st['Title']),
        Spacer(1, 4),
        Paragraph(subtitle, st['Sub']) if subtitle else Spacer(1, 0),
    ]

    if score_val:
        # Build hex string without leading '#' for ReportLab font color tag
        if hasattr(score_color, 'hexval'):
            hex_str = score_color.hexval().lstrip('#')
        else:
            hex_str = 'ffffff'
        score_cell = [
            Paragraph(score_label, st['ScLbl']),
            Paragraph(f'<font color="#{hex_str}">{score_val}</font>', st['Score']),
        ]
        data = [[score_cell, title_cell]]
        col_w = [90, BODY_W - 90]
    else:
        data = [[title_cell]]
        col_w = [BODY_W]

    t = Table(data, colWidths=col_w)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), NAVY),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING',(0,0), (-1,-1), 12),
        ('RIGHTPADDING',(0,0),(-1,-1), 12),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING',(0,0),(-1,-1), 12),
    ]))
    return t


def _score_bar(label: str, score: float, max_score: float, sublabel: str = '') -> Table:
    """Horizontal progress bar row."""
    st = _styles()
    pct = min(100, max(0, score / max_score * 100)) if max_score else 0
    bar_w = BODY_W - 160 - 60   # label=160, value=60
    filled = max(2, bar_w * pct / 100)
    empty  = bar_w - filled
    color  = _score_color(score / max_score * 100) if max_score else SLATE

    label_cell = Paragraph(
        f'{label}<br/><font size="8" color="#94a3b8">{sublabel}</font>' if sublabel else label,
        st['Bold']
    )

    # Bar made from a 2-cell inner table
    bar_inner = Table(
        [['', '']],
        colWidths=[filled, empty],
        rowHeights=[10]
    )
    bar_inner.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), color),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor('#f1f5f9')),
        ('LEFTPADDING', (0,0),(-1,-1), 0),
        ('RIGHTPADDING',(0,0),(-1,-1), 0),
        ('TOPPADDING',  (0,0),(-1,-1), 0),
        ('BOTTOMPADDING',(0,0),(-1,-1),0),
    ]))

    val_cell = Paragraph(f'{score:.0f}/{max_score:.0f}', st['Bold'])

    row = Table([[label_cell, bar_inner, val_cell]],
                colWidths=[160, bar_w, 60])
    row.setStyle(TableStyle([
        ('VALIGN',       (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING',  (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING',   (0,0), (-1,-1), 3),
        ('BOTTOMPADDING',(0,0), (-1,-1), 3),
    ]))
    return row


def _info_box(content_para, border_color=BLUE, bg_color=None) -> Table:
    if bg_color is None:
        bg_color = colors.HexColor('#eff6ff')
    if isinstance(content_para, str):
        content_para = Paragraph(content_para, _styles()['Body'])
    t = Table([[content_para]], colWidths=[BODY_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,-1), bg_color),
        ('LEFTPADDING',  (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING',   (0,0), (-1,-1), 8),
        ('BOTTOMPADDING',(0,0), (-1,-1), 8),
        ('LINEAFTER',    (0,0), (0,-1), 4, border_color),
    ]))
    return t


def _issue_card(issue: dict) -> KeepTogether:
    st   = _styles()
    sev  = issue.get('severity_level', 'low')
    col  = _severity_color(sev)
    bg   = {'high': colors.HexColor('#fef2f2'),
            'moderate': colors.HexColor('#fffbeb'),
            'medium':   colors.HexColor('#fffbeb')}.get(sev.lower(), colors.HexColor('#eff6ff'))

    title = issue.get('issue_title', '')
    expl  = issue.get('explanation', '')
    fix   = issue.get('how_to_fix', '')
    items = issue.get('action_items', []) or []

    paras = [Paragraph(f'<b>{title}</b>  <font size="8">[{sev.upper()}]</font>', st['Bold'])]
    if expl:
        paras.append(Paragraph(expl, st['Body']))
    if fix:
        paras.append(Paragraph(f'<b>Fix:</b> {fix}', st['Small']))
    for a in items:
        paras.append(Paragraph(f'• {a}', st['Small']))

    content_table = Table([[paras]], colWidths=[BODY_W - 4])
    content_table.setStyle(TableStyle([
        ('BACKGROUND',   (0,0), (-1,-1), bg),
        ('LEFTPADDING',  (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING',   (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 6),
        ('LINEAFTER',    (0,0), (0,-1), 4, col),
    ]))
    return KeepTogether([content_table, Spacer(1, 6)])


def _footer_line(report_label: str):
    st = _styles()
    t = Table(
        [[Paragraph('Generated by ATS Resume Scorer', st['Footer']),
          Paragraph(report_label, ParagraphStyle('FR', parent=st['Footer'], alignment=TA_RIGHT))]],
        colWidths=[BODY_W / 2, BODY_W / 2]
    )
    t.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 0),
        ('LINEABOVE',    (0,0),(-1,0),  0.5, SLATE),
    ]))
    return t


# ─── Report builders ──────────────────────────────────────────────────────────

def _build_summary(ctx: Dict) -> List:
    st      = _styles()
    overall = ctx['overall_score']
    cs      = ctx['component_scores']
    sc      = _score_color(overall)
    now_str = datetime.now().strftime('%B %d, %Y  %I:%M %p')

    interp = ctx.get('interpretation', '')
    if not interp:
        if overall >= 80:   interp = "Great! Your resume should perform well with most ATS systems."
        elif overall >= 60: interp = "Good start — a few improvements will boost your score significantly."
        else:               interp = "Your resume needs work. Follow the recommendations below."

    elems: List = []
    elems.append(_header_table('ATS Resume Score Report', now_str,
                               'OVERALL ATS SCORE', f'{overall:.0f}/100', sc))
    elems.append(Spacer(1, 8))
    elems.append(Paragraph(f'<i>{interp}</i>', st['Body']))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph('Score Breakdown', st['H2']))
    elems.append(HRFlowable(width=BODY_W, color=colors.HexColor('#e2e8f0'), thickness=1))
    elems.append(Spacer(1, 6))
    for label, key, max_s, sub in [
        ('Formatting',        'formatting',       20, 'Structure, headers, bullet points'),
        ('Keywords & Skills', 'keywords',         25, 'Keyword density and relevance'),
        ('Content Quality',   'content',          25, 'Action verbs, metrics, achievements'),
        ('Skill Validation',  'skill_validation', 15, 'Skills backed by project evidence'),
        ('ATS Compatibility', 'ats_compatibility',15, 'Clean format, no parsing blockers'),
    ]:
        elems.append(_score_bar(label, cs[key], max_s, sub))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph('Strengths', st['H2']))
    elems.append(HRFlowable(width=BODY_W, color=colors.HexColor('#e2e8f0'), thickness=1))
    elems.append(Spacer(1, 6))
    strengths = ctx.get('strengths', [])
    if strengths:
        for s in strengths:
            elems.append(_info_box(Paragraph(f'✓  {s}', st['Body']), GREEN, colors.HexColor('#f0fdf4')))
    else:
        elems.append(_info_box(Paragraph('No major strengths detected yet — work through the recommendations.', st['Body']), SLATE, LIGHT))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph('Critical Issues', st['H2']))
    elems.append(HRFlowable(width=BODY_W, color=colors.HexColor('#e2e8f0'), thickness=1))
    elems.append(Spacer(1, 6))
    high = ctx.get('high_priority', [])
    if high:
        for issue in high:
            elems.append(_issue_card(issue))
    else:
        elems.append(_info_box(Paragraph('No critical issues found. Review medium-priority recommendations.', st['Body']), GREEN, colors.HexColor('#f0fdf4')))

    elems.append(Spacer(1, 14))
    elems.append(_footer_line('Report 1 of 4 — Score Summary'))
    return elems


def _build_feedback(ctx: Dict) -> List:
    st = _styles()
    all_fb = ctx.get('all_feedback', [])
    vs     = ctx.get('validated_skills', [])
    uvs    = ctx.get('unvalidated_skills', [])
    total  = ctx.get('total_skills', 0)
    vc     = ctx.get('validated_count', 0)
    vpct   = ctx.get('validation_pct', 0.0)

    elems: List = [PageBreak()]
    elems.append(_header_table('Detailed Feedback & Action Items', 'Report 2 of 4'))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph(f'All Issues ({len(all_fb)} found)', st['H2']))
    elems.append(HRFlowable(width=BODY_W, color=colors.HexColor('#e2e8f0'), thickness=1))
    elems.append(Spacer(1, 6))
    if all_fb:
        for fb in all_fb:
            elems.append(_issue_card(fb))
    else:
        elems.append(_info_box(Paragraph('No detailed feedback available.', st['Body']), SLATE, LIGHT))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph('Skill Validation', st['H2']))
    elems.append(HRFlowable(width=BODY_W, color=colors.HexColor('#e2e8f0'), thickness=1))
    elems.append(Spacer(1, 6))
    elems.append(_info_box(
        Paragraph(f'<b>{vc} / {total}</b> skills validated &nbsp; ({vpct:.0f}%)', st['Body']),
        BLUE, colors.HexColor('#eff6ff')
    ))
    if vs:
        elems.append(Paragraph('Validated Skills (backed by evidence)', st['H3']))
        for sv in vs[:20]:
            skill = sv.get('skill', sv) if isinstance(sv, dict) else sv
            projs = ', '.join((sv.get('projects') or [])[:3]) if isinstance(sv, dict) else ''
            elems.append(Paragraph(f'• <b>{skill}</b>' + (f'  <font color="#64748b">— {projs}</font>' if projs else ''), st['Body']))
    if uvs:
        elems.append(Spacer(1, 6))
        elems.append(Paragraph('Unvalidated Skills (listed but not demonstrated)', st['H3']))
        for s in uvs[:20]:
            elems.append(Paragraph(f'• {s}', st['Body']))

    elems.append(Spacer(1, 14))
    elems.append(_footer_line('Report 2 of 4 — Detailed Feedback'))
    return elems


def _build_quick_actions(ctx: Dict) -> List:
    st     = _styles()
    high   = ctx.get('high_priority', [])
    medium = ctx.get('medium_priority', [])
    low    = ctx.get('low_priority', [])

    def _table(items, hdr_color):
        if not items:
            return [Paragraph('None', st['Small'])]
        rows = [
            [Paragraph('<b>Issue</b>', ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=9, textColor=WHITE)),
             Paragraph('<b>Quick Fix</b>', ParagraphStyle('TH2', fontName='Helvetica-Bold', fontSize=9, textColor=WHITE))]
        ]
        for i in items:
            rows.append([
                Paragraph(i.get('issue_title', ''), st['Small']),
                Paragraph(i.get('how_to_fix', ''), st['Small']),
            ])
        t = Table(rows, colWidths=[BODY_W * 0.38, BODY_W * 0.62])
        style_cmds = [
            ('BACKGROUND',   (0,0), (-1,0),  hdr_color),
            ('BACKGROUND',   (0,1), (-1,-1), LIGHT),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),  [WHITE, LIGHT]),
            ('GRID',         (0,0), (-1,-1), 0.3, colors.HexColor('#e2e8f0')),
            ('LEFTPADDING',  (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING',   (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0), (-1,-1), 4),
            ('VALIGN',       (0,0), (-1,-1), 'TOP'),
        ]
        t.setStyle(TableStyle(style_cmds))
        return [t]

    elems: List = [PageBreak()]
    elems.append(_header_table('Quick Actions Checklist', 'Report 3 of 4'))
    elems.append(Spacer(1, 10))

    for label, items, col in [
        (f'High Priority  ({len(high)} issues)',   high,   RED),
        (f'Medium Priority ({len(medium)} issues)', medium, AMBER),
        (f'Low Priority  ({len(low)} issues)',     low,    BLUE),
    ]:
        elems.append(Paragraph(label, st['H2']))
        elems.append(HRFlowable(width=BODY_W, color=colors.HexColor('#e2e8f0'), thickness=1))
        elems.append(Spacer(1, 4))
        elems.extend(_table(items, col))
        elems.append(Spacer(1, 10))

    elems.append(_footer_line('Report 3 of 4 — Quick Actions'))
    return elems


def _build_jd_comparison(ctx: Dict) -> List:
    st = _styles()
    jd = ctx.get('jd_analysis')

    elems: List = [PageBreak()]
    if not jd:
        elems.append(_header_table('Job Description Comparison', 'Report 4 of 4'))
        elems.append(Spacer(1, 12))
        elems.append(_info_box(
            Paragraph('<b>No Job Description Provided</b><br/>Re-run the analysis with a job description to see keyword match and skills gap.', st['Body']),
            BLUE, colors.HexColor('#eff6ff')
        ))
        elems.append(Spacer(1, 14))
        elems.append(_footer_line('Report 4 of 4 — JD Comparison'))
        return elems

    match_pct = float(jd.get('match_percentage', 0) or 0)
    sem_sim   = float(jd.get('semantic_similarity', 0) or 0)
    matched   = list(jd.get('matched_keywords', []) or [])[:25]
    missing   = list(jd.get('missing_keywords', []) or [])[:25]
    gap       = list(jd.get('skills_gap', []) or [])[:15]
    sc        = _score_color(match_pct)

    elems.append(_header_table('Job Description Comparison',
                               f'Report 4 of 4  |  Semantic similarity: {sem_sim:.1%}',
                               'JD MATCH', f'{match_pct:.0f}%', sc))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph(f'Matched Keywords ({len(matched)})', st['H2']))
    elems.append(HRFlowable(width=BODY_W, color=colors.HexColor('#e2e8f0'), thickness=1))
    elems.append(Spacer(1, 4))
    if matched:
        for k in matched:
            elems.append(Paragraph(f'• {k}', st['Body']))
    else:
        elems.append(Paragraph('None matched yet.', st['Small']))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph(f'Missing Keywords ({len(missing)})', st['H2']))
    elems.append(HRFlowable(width=BODY_W, color=colors.HexColor('#e2e8f0'), thickness=1))
    elems.append(Spacer(1, 4))
    if missing:
        for k in missing:
            elems.append(Paragraph(f'• {k}', st['Body']))
    else:
        elems.append(Paragraph('None missing — great match!', st['Small']))
    elems.append(Spacer(1, 10))

    if gap:
        elems.append(Paragraph('Skills Gap', st['H2']))
        elems.append(HRFlowable(width=BODY_W, color=colors.HexColor('#e2e8f0'), thickness=1))
        elems.append(Spacer(1, 4))
        for k in gap:
            elems.append(Paragraph(f'• {k}', st['Body']))
        elems.append(Spacer(1, 10))

    elems.append(_footer_line('Report 4 of 4 — JD Comparison'))
    return elems


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_pdf(analysis_data: Dict) -> bytes:
    """
    Generate a complete 4-section PDF report from an analysis result dict.
    Uses ReportLab Platypus directly — no HTML, no WeasyPrint, no xhtml2pdf.
    """
    # Normalise input
    overall_score = float(
        analysis_data.get('ATS_score') or analysis_data.get('ats_score') or 0
    )
    cs_raw = analysis_data.get('component_scores') or {}
    if hasattr(cs_raw, 'model_dump'):  cs_raw = cs_raw.model_dump()
    elif hasattr(cs_raw, '__dict__'):  cs_raw = cs_raw.__dict__

    max_map = {'formatting': 20, 'keywords': 25, 'content': 25,
               'skill_validation': 15, 'ats_compatibility': 15}
    component_scores = {k: float(cs_raw.get(k) or 0) for k in max_map}

    def _to_dict(item):
        if isinstance(item, dict): return item
        return item.model_dump() if hasattr(item, 'model_dump') else vars(item)

    raw_fb = analysis_data.get('detailed_feedback') or []
    all_fb = [_to_dict(fb) for fb in raw_fb]

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
        'strengths':          list(analysis_data.get('strengths') or []),
        'high_priority':      [fb for fb in all_fb if fb.get('severity_level','').lower() == 'high'],
        'medium_priority':    [fb for fb in all_fb if fb.get('severity_level','').lower() in ('moderate','medium')],
        'low_priority':       [fb for fb in all_fb if fb.get('severity_level','').lower() in ('low','info')],
        'all_feedback':       all_fb,
        'validated_skills':   list(svd_raw.get('validated') or []),
        'unvalidated_skills': list(svd_raw.get('unvalidated') or []),
        'total_skills':       int(svd_raw.get('total') or 0),
        'validated_count':    int(svd_raw.get('validated_count') or 0),
        'validation_pct':     float(svd_raw.get('validation_pct') or 0),
        'jd_analysis':        jd_raw,
    }

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN,
    )

    story = []
    story.extend(_build_summary(ctx))
    story.extend(_build_feedback(ctx))
    story.extend(_build_quick_actions(ctx))
    story.extend(_build_jd_comparison(ctx))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    logger.info(f'ReportLab PDF generated: {len(pdf_bytes)} bytes')
    return pdf_bytes
