"""
Report Generator API Route
===========================
Exports analysis results as JSON or formatted PDF files.
PDF uses a premium, brand-consistent design with ReportLab's canvas API.
"""

import json
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from app.database import get_db, AnalysisResult

router = APIRouter(prefix="/api/report", tags=["Report"])

# ─── Brand Colors ─────────────────────────────────────────────────
C_PRIMARY    = colors.HexColor('#6366f1')  # Indigo
C_ACCENT     = colors.HexColor('#06b6d4')  # Cyan
C_SUCCESS    = colors.HexColor('#10b981')  # Green
C_CRITICAL   = colors.HexColor('#ef4444')  # Red
C_HIGH       = colors.HexColor('#f97316')  # Orange
C_MEDIUM     = colors.HexColor('#eab308')  # Yellow
C_LOW        = colors.HexColor('#3b82f6')  # Blue
C_BG_DARK    = colors.HexColor('#0a0a0a')
C_BG_CARD    = colors.HexColor('#161616')
C_BORDER     = colors.HexColor('#2a2a2a')
C_TEXT_MUT   = colors.HexColor('#94a3b8')
C_TEXT_SEC   = colors.HexColor('#64748b')
C_WHITE      = colors.white
C_LIGHT_BG   = colors.HexColor('#f8fafc')
C_HEADER_BG  = colors.HexColor('#1e1b4b')  # Deep indigo for header band


SEV_COLOR = {
    'critical': C_CRITICAL,
    'high':     C_HIGH,
    'medium':   C_MEDIUM,
    'low':      C_LOW,
    'info':     C_TEXT_MUT,
}

SEV_LIGHT_BG = {
    'critical': colors.HexColor('#fef2f2'),
    'high':     colors.HexColor('#fff7ed'),
    'medium':   colors.HexColor('#fefce8'),
    'low':      colors.HexColor('#eff6ff'),
    'info':     colors.HexColor('#f8fafc'),
}


def get_score_color(score):
    if score >= 80:
        return C_SUCCESS
    if score >= 60:
        return C_MEDIUM
    if score >= 40:
        return C_HIGH
    return C_CRITICAL


def get_grade(score):
    if score >= 90: return 'A'
    if score >= 80: return 'B'
    if score >= 70: return 'C'
    if score >= 60: return 'D'
    return 'F'


# ─── Canvas page decorator (header band + footer) ─────────────────
class BrandedCanvas(canvas.Canvas):
    def __init__(self, *args, repo_name="", date_str="", **kwargs):
        super().__init__(*args, **kwargs)
        self.repo_name = repo_name
        self.date_str = date_str
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_chrome(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_chrome(self, page_count):
        page_num = self._pageNumber
        w, h = letter

        # ─── Header band (only on page 1) ───────────────────────────
        if page_num == 1:
            # Dark header gradient band
            self.setFillColor(C_HEADER_BG)
            self.rect(0, h - 100, w, 100, fill=1, stroke=0)

            # Accent stripe
            self.setFillColor(C_PRIMARY)
            self.rect(0, h - 104, w, 4, fill=1, stroke=0)

            # Logo text
            self.setFont('Helvetica-Bold', 22)
            self.setFillColor(C_WHITE)
            self.drawString(40, h - 52, 'CodeAutopsy')

            # Tagline
            self.setFont('Helvetica', 10)
            self.setFillColor(colors.HexColor('#a5b4fc'))
            self.drawString(40, h - 70, 'AI-Powered Security & Quality Analysis')

            # Repo pill on right
            self.setFont('Helvetica', 9)
            self.setFillColor(colors.HexColor('#818cf8'))
            repo_display = self.repo_name if len(self.repo_name) < 45 else '...' + self.repo_name[-42:]
            self.drawRightString(w - 40, h - 52, repo_display)
            self.setFillColor(colors.HexColor('#4f46e5'))
            self.setFont('Helvetica', 8)
            self.drawRightString(w - 40, h - 68, self.date_str)
        else:
            # Slim header for subsequent pages
            self.setFillColor(C_HEADER_BG)
            self.rect(0, h - 36, w, 36, fill=1, stroke=0)
            self.setFillColor(C_PRIMARY)
            self.rect(0, h - 38, w, 2, fill=1, stroke=0)
            self.setFont('Helvetica-Bold', 9)
            self.setFillColor(colors.HexColor('#a5b4fc'))
            self.drawString(40, h - 24, 'CodeAutopsy Analysis Report')
            self.setFont('Helvetica', 8)
            self.setFillColor(colors.HexColor('#6366f1'))
            self.drawRightString(w - 40, h - 24, self.repo_name)

        # ─── Footer ──────────────────────────────────────────────────
        self.setFillColor(colors.HexColor('#f1f5f9'))
        self.rect(0, 0, w, 32, fill=1, stroke=0)
        self.setFillColor(C_PRIMARY)
        self.rect(0, 32, w, 1, fill=1, stroke=0)

        self.setFont('Helvetica', 7.5)
        self.setFillColor(C_TEXT_SEC)
        self.drawString(40, 12, f'Generated by CodeAutopsy AI  •  {self.date_str}')
        self.drawRightString(w - 40, 12, f'Page {page_num} of {page_count}')


# ─── Helpers ──────────────────────────────────────────────────────
def _make_styles():
    base = getSampleStyleSheet()
    return {
        'section': ParagraphStyle(
            'Section', parent=base['Heading2'],
            fontSize=14, fontName='Helvetica-Bold',
            textColor=C_PRIMARY, spaceBefore=24, spaceAfter=10,
            borderPad=0,
        ),
        'body': ParagraphStyle(
            'Body', parent=base['Normal'],
            fontSize=9, textColor=colors.HexColor('#374151'),
            spaceAfter=4,
        ),
        'mono': ParagraphStyle(
            'Mono', parent=base['Normal'],
            fontName='Courier', fontSize=8,
            textColor=colors.HexColor('#374151'),
        ),
        'center': ParagraphStyle(
            'Center', parent=base['Normal'],
            alignment=TA_CENTER, fontSize=9,
            textColor=C_TEXT_SEC,
        ),
        'caption': ParagraphStyle(
            'Caption', parent=base['Normal'],
            fontSize=8, textColor=C_TEXT_SEC, spaceAfter=2,
        ),
    }


# ─── JSON Export ──────────────────────────────────────────────────
@router.get("/{analysis_id}/json")
async def export_json(analysis_id: str, db: Session = Depends(get_db)):
    """Export the full analysis result as a JSON file."""
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.status != "complete":
        raise HTTPException(status_code=400, detail="Analysis is not yet complete")

    issues = analysis.get_issues()
    sev_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for i in issues:
        s = i.get("severity", "info")
        sev_summary[s] = sev_summary.get(s, 0) + 1

    analyzed_at = (
        analysis.completed_at.isoformat() if analysis.completed_at
        else (analysis.created_at.isoformat() if analysis.created_at
              else datetime.utcnow().isoformat())
    )

    export_data = {
        "metadata": {
            "repository": analysis.repo_url,
            "analysis_id": analysis.id,
            "analyzed_at": analyzed_at,
            "generator": "CodeAutopsy AI"
        },
        "summary": {
            "health_score": analysis.health_score or 0,
            "total_files": analysis.file_count or 0,
            "total_lines": analysis.total_lines or 0,
            "total_issues": analysis.total_issues or 0,
            "severity_summary": sev_summary
        },
        "issues": issues,
        "file_tree": analysis.get_file_tree()
    }
    return Response(
        content=json.dumps(export_data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="codeautopsy_report_{analysis_id[:8]}.json"'}  # type: ignore
    )


# ─── PDF Export ───────────────────────────────────────────────────
@router.get("/{analysis_id}/pdf")
async def export_pdf(analysis_id: str, db: Session = Depends(get_db)):
    """Export the analysis result as a branded, beautifully formatted PDF report."""
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.status != "complete":
        raise HTTPException(status_code=400, detail="Analysis is not yet complete")

    issues = analysis.get_issues()
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 99))

    repo_name = analysis.repo_url.split('github.com/')[-1].strip('/')
    if analysis.completed_at:
        date_str = analysis.completed_at.strftime("%B %d, %Y at %H:%M UTC")
    elif analysis.created_at:
        date_str = analysis.created_at.strftime("%B %d, %Y at %H:%M UTC")
    else:
        date_str = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")

    # Severity counts
    sev_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for i in issues:
        s = i.get("severity", "info")
        sev_counts[s] = sev_counts.get(s, 0) + 1

    health_score = analysis.health_score or 0
    grade = get_grade(health_score)
    score_color = get_score_color(health_score)

    buffer = BytesIO()
    S = _make_styles()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=116, bottomMargin=48,  # space for header/footer
        title=f"CodeAutopsy Report — {repo_name}",
        author="CodeAutopsy AI",
    )

    def canvas_maker(*args, **kwargs):
        return BrandedCanvas(*args, repo_name=repo_name, date_str=date_str, **kwargs)

    elems = []

    # ─── Executive Summary ───────────────────────────────────────────
    elems.append(Paragraph("Executive Summary", S['section']))

    # Score + stats big table
    score_pct = int((health_score / 100) * 327)  # circumference proxy
    stat_data = [
        ['Health Score', 'Grade', 'Total Issues', 'Files Analyzed', 'Lines of Code'],
        [
            f'{health_score}/100',
            grade,
            str(len(issues)),
            str(analysis.file_count or 0),
            f"{(analysis.total_lines or 0):,}",
        ]
    ]
    col_widths = [1.2*inch, 0.8*inch, 1.2*inch, 1.3*inch, 1.3*inch]
    stat_table = Table(stat_data, colWidths=col_widths, hAlign='LEFT')
    stat_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), C_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#a5b4fc')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        # Data row
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 16),
        ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
        # Score cell color
        ('TEXTCOLOR', (0, 1), (0, 1), score_color),
        ('TEXTCOLOR', (1, 1), (1, 1), score_color),
        # Critical count in red
        ('TEXTCOLOR', (2, 1), (2, 1), C_CRITICAL if sev_counts.get('critical', 0) > 0 else C_SUCCESS),
        ('TEXTCOLOR', (3, 1), (3, 1), colors.HexColor('#374151')),
        ('TEXTCOLOR', (4, 1), (4, 1), colors.HexColor('#374151')),
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, 1), [C_LIGHT_BG]),
    ]))
    elems.append(stat_table)
    elems.append(Spacer(1, 20))

    # ─── Severity Breakdown ──────────────────────────────────────────
    elems.append(Paragraph("Issue Breakdown by Severity", S['section']))

    total_issues_count = max(len(issues), 1)
    sev_rows = []
    for sev in ['critical', 'high', 'medium', 'low', 'info']:
        count = sev_counts.get(sev, 0)
        pct = int((count / total_issues_count) * 100)
        bar_fill = colors.HexColor({'critical': '#ef4444', 'high': '#f97316',
                                     'medium': '#eab308', 'low': '#3b82f6',
                                     'info': '#94a3b8'}[sev])
        sev_rows.append([
            sev.upper(),
            str(count),
            f'{pct}%',
        ])

    sev_bg_map = {
        0: colors.HexColor('#fef2f2'),
        1: colors.HexColor('#fff7ed'),
        2: colors.HexColor('#fefce8'),
        3: colors.HexColor('#eff6ff'),
        4: colors.HexColor('#f8fafc'),
    }
    sev_text_colors = {
        0: C_CRITICAL,
        1: C_HIGH,
        2: colors.HexColor('#a16207'),  # dark yellow
        3: C_LOW,
        4: C_TEXT_MUT,
    }

    sev_header = [['Severity', 'Count', 'Proportion']]
    sev_table = Table(sev_header + sev_rows, colWidths=[1.5*inch, 1*inch, 1*inch], hAlign='LEFT')
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), C_HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#a5b4fc')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]
    for row_i, sev in enumerate(['critical', 'high', 'medium', 'low', 'info']):
        r = row_i + 1
        style_cmds.append(('BACKGROUND', (0, r), (-1, r), sev_bg_map[row_i]))
        style_cmds.append(('TEXTCOLOR', (0, r), (0, r), sev_text_colors[row_i]))
    sev_table.setStyle(TableStyle(style_cmds))
    elems.append(sev_table)
    elems.append(Spacer(1, 24))

    # ─── Issues Table ────────────────────────────────────────────────
    elems.append(Paragraph("Detected Issues (Top 100)", S['section']))

    if not issues:
        elems.append(Paragraph(
            "<font color='#10b981'>✓ No issues found in this repository. Excellent work!</font>",
            S['body']
        ))
    else:
        # Table header
        issue_header = [['#', 'Severity', 'Type', 'File', 'Line']]
        issue_rows = []

        for idx, issue in enumerate(issues[:100], 1):
            file_name = issue.get('file_path', '')
            # Shorten path: keep last 2 segments
            parts = file_name.replace('\\', '/').split('/')
            file_display = '/'.join(parts[-2:]) if len(parts) > 1 else file_name
            if len(file_display) > 32:
                file_display = '…' + file_display[-30:]  # type: ignore

            sev = issue.get('severity', 'info')
            issue_type = issue.get('issue_type', 'unknown')
            if len(issue_type) > 28:
                issue_type = issue_type[:26] + '…'

            issue_rows.append([
                str(idx),
                sev.upper(),
                issue_type,
                file_display,
                str(issue.get('line_number', '?')),
            ])

        issue_table = Table(
            issue_header + issue_rows,
            colWidths=[0.35*inch, 0.75*inch, 2.3*inch, 2.3*inch, 0.45*inch],
            hAlign='LEFT',
            repeatRows=1,
        )

        issue_style_cmds = [
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), C_HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#a5b4fc')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            # Data
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (0, 1), (1, -1), 'CENTER'),
            ('ALIGN', (-1, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (3, 1), (3, -1), 'Courier'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]

        # Row shading and severity coloring
        sev_abbrev_colors = {
            'CRITICAL': C_CRITICAL,
            'HIGH': C_HIGH,
            'MEDIUM': colors.HexColor('#a16207'),
            'LOW': C_LOW,
            'INFO': C_TEXT_MUT,
        }
        for row_i, issue in enumerate(issues[:100], 1):
            sev = issue.get('severity', 'info').upper()
            sev_c = sev_abbrev_colors.get(sev, C_TEXT_MUT)
            # Alternating row background
            if row_i % 2 == 0:
                issue_style_cmds.append(('BACKGROUND', (0, row_i), (-1, row_i), colors.HexColor('#f9fafb')))
            # Severity text color
            issue_style_cmds.append(('TEXTCOLOR', (1, row_i), (1, row_i), sev_c))
            issue_style_cmds.append(('FONTNAME', (1, row_i), (1, row_i), 'Helvetica-Bold'))

        issue_table.setStyle(TableStyle(issue_style_cmds))
        elems.append(issue_table)

        if len(issues) > 100:
            elems.append(Spacer(1, 8))
            elems.append(Paragraph(
                f"<i>… and {len(issues) - 100} more issues not shown in this summary report.</i>",
                S['caption']
            ))

    elems.append(Spacer(1, 32))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e5e7eb')))
    elems.append(Spacer(1, 8))
    elems.append(Paragraph(
        f"This report was generated automatically by CodeAutopsy AI. "
        f"Repository: <b>{repo_name}</b>  •  Analysis ID: {analysis_id[:8]}",  # type: ignore
        S['caption']
    ))

    doc.build(elems, canvasmaker=canvas_maker)

    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="codeautopsy_{repo_name.replace("/", "_")}.pdf"'
        }
    )
