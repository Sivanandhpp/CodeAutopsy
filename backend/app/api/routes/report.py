"""
Report Generator API Route (Async + Auth)
==========================================
Exports analysis results as JSON or formatted PDF files.
PDF uses a premium, brand-consistent design with ReportLab.
"""

import json
import logging
from datetime import datetime, timezone
from io import BytesIO
from collections import Counter
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, String, Group
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER

from app.database import get_db
from app.models.analysis import AnalysisResult
from app.models.user import User
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/report", tags=["Report"])

# ─── Brand Colors ────────────────────────────────────────────
C_PRIMARY = colors.HexColor('#1d1d1f')     # High contrast black/gray
C_ACCENT = colors.HexColor('#0066cc')      # Apple Blue
C_SUCCESS = colors.HexColor('#34c759')     # Apple Green
C_BLOCKER = colors.HexColor('#ff3b30')     # Apple Red
C_CRITICAL = colors.HexColor('#ff3b30')
C_HIGH = colors.HexColor('#ff9500')        # Apple Orange
C_MEDIUM = colors.HexColor('#ffcc00')      # Apple Yellow
C_LOW = colors.HexColor('#5ac8fa')         # Apple Light Blue
C_WHITE = colors.white
C_LIGHT_BG = colors.HexColor('#f5f5f7')    # Apple Light Gray
C_HEADER_BG = colors.HexColor('#ffffff')   # Clean white
C_TEXT_SEC = colors.HexColor('#86868b')
C_TEXT_MUT = colors.HexColor('#86868b')

SEV_COLOR = {
    'blocker': C_BLOCKER,
    'critical': C_CRITICAL,
    'high': C_HIGH,
    'medium': C_MEDIUM,
    'low': C_LOW,
    'info': C_TEXT_MUT,
    'trace': C_TEXT_MUT,
}


def get_score_color(score):
    if score >= 80: return C_SUCCESS
    if score >= 60: return C_MEDIUM
    if score >= 40: return C_HIGH
    return C_CRITICAL


def get_grade(score):
    if score >= 90: return 'A'
    if score >= 80: return 'B'
    if score >= 70: return 'C'
    if score >= 60: return 'D'
    return 'F'


def get_risk_label(sev_counts: dict) -> tuple[str, colors.Color]:
    if sev_counts.get('blocker', 0) > 0:
        return "Blocker risks present", C_BLOCKER
    if sev_counts.get('critical', 0) > 0:
        return "Critical risks present", C_CRITICAL
    if sev_counts.get('high', 0) > 0:
        return "High-risk issues detected", C_HIGH
    if sev_counts.get('medium', 0) > 0:
        return "Moderate-risk issues", C_MEDIUM
    return "Low overall risk", C_SUCCESS


def format_ai_summary(summary: str) -> str:
    if not summary:
        return ""
    formatted = []
    for line in summary.splitlines():
        text = line.strip()
        if not text:
            formatted.append("")
            continue
        if text.startswith("#"):
            formatted.append(f"<b>{escape(text.lstrip('#').strip())}</b>")
            continue
        if text.startswith(('-', '*', '•')):
            formatted.append(f"• {escape(text.lstrip('-*•').strip())}")
            continue
        formatted.append(escape(text))
    return "<br/>".join(formatted)


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

        if page_num == 1:
            self.setFillColor(C_HEADER_BG)
            self.rect(0, h - 100, w, 100, fill=1, stroke=0)
            self.setFillColor(colors.HexColor('#d2d2d7'))
            self.rect(0, h - 100, w, 1, fill=1, stroke=0)
            self.setFont('Helvetica-Bold', 24)
            self.setFillColor(colors.HexColor('#1d1d1f'))
            self.drawString(40, h - 52, 'CodeAutopsy')
            self.setFont('Helvetica', 10)
            self.setFillColor(C_TEXT_SEC)
            self.drawString(40, h - 70, 'AI-Powered Security & Quality Analysis')
            self.setFont('Helvetica', 9)
            self.setFillColor(colors.HexColor('#1d1d1f'))
            repo_display = self.repo_name if len(self.repo_name) < 45 else '...' + self.repo_name[-42:]
            self.drawRightString(w - 40, h - 52, repo_display)
            self.setFillColor(C_TEXT_SEC)
            self.setFont('Helvetica', 8)
            self.drawRightString(w - 40, h - 68, self.date_str)
        else:
            self.setFillColor(C_HEADER_BG)
            self.rect(0, h - 40, w, 40, fill=1, stroke=0)
            self.setFillColor(colors.HexColor('#d2d2d7'))
            self.rect(0, h - 40, w, 1, fill=1, stroke=0)
            self.setFont('Helvetica-Bold', 9)
            self.setFillColor(colors.HexColor('#1d1d1f'))
            self.drawString(40, h - 24, 'CodeAutopsy Analysis Report')
            self.setFont('Helvetica', 8)
            self.setFillColor(C_TEXT_SEC)
            self.drawRightString(w - 40, h - 24, self.repo_name)

        self.setFillColor(colors.HexColor('#ffffff'))
        self.rect(0, 0, w, 32, fill=1, stroke=0)
        self.setFillColor(colors.HexColor('#d2d2d7'))
        self.rect(0, 32, w, 1, fill=1, stroke=0)
        self.setFont('Helvetica', 8)
        self.setFillColor(C_TEXT_SEC)
        self.drawString(40, 12, f'Generated by CodeAutopsy AI  •  {self.date_str}')
        self.drawRightString(w - 40, 12, f'Page {page_num} of {page_count}')


def _make_styles():
    base = getSampleStyleSheet()
    return {
        'section': ParagraphStyle(
            'Section', parent=base['Heading2'],
            fontSize=14, fontName='Helvetica-Bold',
            textColor=C_PRIMARY, spaceBefore=24, spaceAfter=10,
        ),
        'subsection': ParagraphStyle(
            'SubSection', parent=base['Heading3'],
            fontSize=11, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1d1d1f'), spaceBefore=12, spaceAfter=6,
        ),
        'body': ParagraphStyle(
            'Body', parent=base['Normal'],
            fontSize=9, textColor=colors.HexColor('#374151'), spaceAfter=4,
        ),
        'body_sm': ParagraphStyle(
            'BodySm', parent=base['Normal'],
            fontSize=8.5, textColor=colors.HexColor('#475569'), leading=12,
        ),
        'callout_title': ParagraphStyle(
            'CalloutTitle', parent=base['Heading3'],
            fontSize=11, fontName='Helvetica-Bold',
            textColor=C_PRIMARY, spaceBefore=0, spaceAfter=6,
        ),
        'callout_body': ParagraphStyle(
            'CalloutBody', parent=base['Normal'],
            fontSize=9.2, textColor=colors.HexColor('#1f2937'), leading=14,
        ),
        'caption': ParagraphStyle(
            'Caption', parent=base['Normal'],
            fontSize=8, textColor=C_TEXT_SEC, spaceAfter=2,
        ),
    }


# ─── JSON Export ─────────────────────────────────────────────

@router.get("/{analysis_id}/json")
async def export_json(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export analysis result as a JSON file."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.status != "complete":
        raise HTTPException(status_code=400, detail="Analysis is not yet complete")

    issues = analysis.get_issues()
    sev_summary = {
        "blocker": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
        "trace": 0,
    }
    for i in issues:
        s = i.get("severity", "info")
        sev_summary[s] = sev_summary.get(s, 0) + 1

    contributor_data = analysis.get_contributor_stats()
    
    # Fallback to simple counts if contributor_data is somehow missing
    user_counts = {}
    if not contributor_data:
        for i in issues:
            author = i.get("origin_author", "unknown")
            user_counts[author] = user_counts.get(author, 0) + 1

    analyzed_at = (
        analysis.completed_at.isoformat() if analysis.completed_at
        else (analysis.created_at.isoformat() if analysis.created_at
              else datetime.now(timezone.utc).isoformat())
    )

    export_data = {
        "metadata": {
            "repository": analysis.repo_url,
            "analysis_id": analysis.id,
            "analyzed_at": analyzed_at,
            "generator": "CodeAutopsy AI v2.0",
        },
        "summary": {
            "health_score": analysis.health_score or 0,
            "total_files": analysis.file_count or 0,
            "total_lines": analysis.total_lines or 0,
            "total_issues": analysis.total_issues or 0,
            "severity_summary": sev_summary,
            "user_stats": user_counts if not contributor_data else {k: v.get("count", 0) for k, v in contributor_data.items()},
        },
        "contributors": contributor_data,
        "issues": issues,
        "ollama_findings": analysis.get_ollama_findings(),
        "file_tree": analysis.get_file_tree(),
    }

    return Response(
        content=json.dumps(export_data, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="codeautopsy_report_{analysis_id[:8]}.json"'
            )
        },
    )


# ─── PDF Export ──────────────────────────────────────────────

@router.get("/{analysis_id}/pdf")
async def export_pdf(
    analysis_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export analysis result as a branded PDF report."""
    result = await db.execute(
        select(AnalysisResult).where(AnalysisResult.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    if analysis.status != "complete":
        raise HTTPException(status_code=400, detail="Analysis is not yet complete")

    issues = analysis.get_issues()
    severity_order = {
        "blocker": 0,
        "critical": 1,
        "high": 2,
        "medium": 3,
        "low": 4,
        "info": 5,
        "trace": 6,
    }
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 99))

    repo_name = analysis.repo_url.split('github.com/')[-1].strip('/')
    if analysis.completed_at:
        date_str = analysis.completed_at.strftime("%B %d, %Y at %H:%M UTC")
    elif analysis.created_at:
        date_str = analysis.created_at.strftime("%B %d, %Y at %H:%M UTC")
    else:
        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    sev_counts = {
        "blocker": 0,
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
        "trace": 0,
    }
    for i in issues:
        s = i.get("severity", "info")
        sev_counts[s] = sev_counts.get(s, 0) + 1

    family_counts = Counter()
    user_counts = {}
    for i in issues:
        family = i.get("defect_family", "unknown") or "unknown"
        family_counts[family] += 1
        
        author = i.get("origin_author", "Unknown Developer")
        user_counts[author] = user_counts.get(author, 0) + 1

    top_families = family_counts.most_common(8)
    top_family_label = top_families[0][0] if top_families else "None"

    lang_counts = analysis.get_languages()
    top_languages = ", ".join(list(lang_counts.keys())[:3]) if lang_counts else "N/A"

    risk_label, risk_color = get_risk_label(sev_counts)

    health_score = analysis.health_score or 0
    grade = get_grade(health_score)
    score_color = get_score_color(health_score)

    buffer = BytesIO()
    S = _make_styles()

    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=116, bottomMargin=48,
        title=f"CodeAutopsy Report — {repo_name}",
        author="CodeAutopsy AI",
    )

    def canvas_maker(*args, **kwargs):
        return BrandedCanvas(*args, repo_name=repo_name, date_str=date_str, **kwargs)

    elems = []

    page_width = 8.5 * 72
    usable_width = page_width - 80 # 40pt margins

    # Executive Summary
    elems.append(Paragraph("Executive Summary", S['section']))
    stat_data = [
        ['Health Score', 'Grade', 'Total Issues', 'Files Analyzed', 'Lines of Code'],
        [f'{health_score}/100', grade, str(len(issues)),
         str(analysis.file_count or 0), f"{(analysis.total_lines or 0):,}"]
    ]
    col_widths = [usable_width * 0.20, usable_width * 0.15, usable_width * 0.20, usable_width * 0.20, usable_width * 0.25]
    stat_table = Table(stat_data, colWidths=col_widths, hAlign='LEFT')
    stat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_LIGHT_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), C_TEXT_SEC),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 16),
        ('TEXTCOLOR', (0, 1), (0, 1), score_color),
        ('TEXTCOLOR', (1, 1), (1, 1), score_color),
        ('TEXTCOLOR', (2, 1), (2, 1),
         C_BLOCKER if sev_counts.get('blocker', 0) > 0
         else (C_CRITICAL if sev_counts.get('critical', 0) > 0 else C_SUCCESS)),
        ('TEXTCOLOR', (3, 1), (3, 1), C_PRIMARY),
        ('TEXTCOLOR', (4, 1), (4, 1), C_PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d2d2d7')),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('ROWBACKGROUNDS', (0, 1), (-1, 1), [C_WHITE]),
    ]))
    elems.append(stat_table)
    elems.append(Spacer(1, 24))

    # Executive Highlights
    highlights = [
        ["Top Risk", "Hotspot Family", "Language Hotspots"],
        [risk_label, top_family_label, top_languages],
    ]
    highlight_table = Table(highlights, colWidths=[usable_width/3.0, usable_width/3.0, usable_width/3.0], hAlign='LEFT')
    highlight_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_LIGHT_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), C_TEXT_SEC),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TEXTCOLOR', (0, 1), (0, 1), risk_color),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d2d2d7')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elems.append(highlight_table)
    elems.append(Spacer(1, 24))

    # Severity Breakdown + Pie Chart Layout
    elems.append(Paragraph("Issue Breakdown by Severity", S['section']))
    
    sev_order = ["blocker", "critical", "high", "medium", "low", "info", "trace"]
    sev_rows = []
    total_issues_count = max(len(issues), 0)
    for sev in sev_order:
        count = sev_counts.get(sev, 0)
        pct = int((count / max(total_issues_count, 1)) * 100)
        sev_rows.append([sev.upper(), str(count), f'{pct}%'])

    sev_header = [['Severity', 'Count', 'Proportion']]
    sev_table_width = usable_width * 0.5
    chart_width = usable_width * 0.5
    
    sev_table = Table(sev_header + sev_rows, colWidths=[sev_table_width*0.4, sev_table_width*0.3, sev_table_width*0.3], hAlign='LEFT')
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), C_LIGHT_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), C_TEXT_SEC),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e5ea')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]
    
    pie_drawing = Drawing(chart_width, 150)
    if total_issues_count > 0:
        pc = Pie()
        pc.x = 20
        pc.y = 15
        pc.width = 120
        pc.height = 120
        active_sevs = []
        pie_data = []
        pie_colors = []
        for sev in sev_order:
            count = sev_counts.get(sev, 0)
            if count > 0:
                active_sevs.append(sev.upper())
                pie_data.append(count)
                pie_colors.append(SEV_COLOR.get(sev, C_TEXT_MUT))
        pc.data = pie_data
        pc.labels = active_sevs
        for i, color in enumerate(pie_colors):
            pc.slices[i].fillColor = color
            pc.slices[i].strokeColor = colors.white
        
        legend = Legend()
        legend.x = 160
        legend.y = 135
        legend.dx = 8
        legend.dy = 8
        legend.fontName = 'Helvetica'
        legend.fontSize = 8
        legend.boxAnchor = 'nw'
        legend.colorNamePairs = list(zip(pie_colors, active_sevs))
        
        pie_drawing.add(pc)
        pie_drawing.add(legend)
    else:
        pie_drawing.add(String(50, 75, "No defects present", fontSize=10, fillColor=C_TEXT_SEC))

    for row_i, sev in enumerate(sev_order):
        r = row_i + 1
        style_cmds.append(('TEXTCOLOR', (0, r), (0, r), SEV_COLOR.get(sev, C_TEXT_MUT)))
    sev_table.setStyle(TableStyle(style_cmds))
    
    layout_table = Table([[sev_table, pie_drawing]], colWidths=[sev_table_width, chart_width], hAlign='LEFT')
    layout_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elems.append(layout_table)
    elems.append(Spacer(1, 24))

    # Defect Family Breakdown
    elems.append(Paragraph("Defect Family Hotspots", S['section']))
    if not top_families:
        elems.append(Paragraph("No defects detected.", S['body']))
    else:
        family_rows = []
        for family, count in top_families:
            pct = int((count / max(total_issues_count, 1)) * 100)
            family_rows.append([family, str(count), f"{pct}%"])
        family_table = Table(
            [["Family", "Count", "Proportion"]] + family_rows,
            colWidths=[usable_width*0.6, usable_width*0.2, usable_width*0.2], hAlign='LEFT'
        )
        family_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_LIGHT_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), C_TEXT_SEC),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e5ea')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        elems.append(family_table)
    elems.append(Spacer(1, 24))

    # User Statistics (Author Error Counts)
    elems.append(Paragraph("User Statistics & Defect Attribution", S['section']))
    
    # Use pre-calculated stats from the DB if available, otherwise fallback to issues
    contributor_data = analysis.get_contributor_stats()
    
    if not contributor_data and issues:
        # Fallback calculation if stats aren't pre-calculated (for legacy records)
        contributor_data = {}
        for issue in issues:
            email = issue.get("origin_author_email") or issue.get("origin_author", "Unknown")
            name = issue.get("origin_author_name") or email.split('<')[0].strip() if '<' in email else email
            if email not in contributor_data:
                contributor_data[email] = {"name": name, "email": email, "count": 0}
            contributor_data[email]["count"] += 1

    if not contributor_data:
        elems.append(Paragraph("No author data available.", S['body']))
    else:
        # Sort by count descending
        sorted_users = sorted(contributor_data.values(), key=lambda x: x['count'], reverse=True)[:10]
        user_rows = []
        user_names = []
        user_data = []
        for user_info in sorted_users:
            display_name = user_info['name']
            email = user_info['email']
            count = user_info['count']
            
            # Format display string for the table
            table_display = f"{display_name}\n<font size=7 color='#86868b'>{email}</font>"
            user_rows.append([Paragraph(table_display, S['body']), str(count)])
            
            # For the chart, we want them bottom-up so highest is at top
            user_names.insert(0, display_name)
            user_data.insert(0, count)
            
        user_table_width = usable_width * 0.5
        chart_width = usable_width * 0.5
            
        user_table = Table(
            [["Author / Developer", "Issues Introduced"]] + user_rows,
            colWidths=[user_table_width * 0.7, user_table_width * 0.3], hAlign='LEFT'
        )
        user_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_LIGHT_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), C_TEXT_SEC),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e5ea')),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ]))
        
        # Horizontal Bar Chart
        bar_drawing = Drawing(chart_width, 150)
        if sum(user_data) > 0:
            bc = HorizontalBarChart()
            bc.x = 80
            bc.y = 15
            bc.height = 120
            bc.width = chart_width - 100
            bc.data = [user_data]
            
            # format labels to prevent overlapping
            clean_names = []
            for name in user_names:
                display = name.split('<')[0].strip() if '<' in name else name
                display = display[:10] + '…' if len(display) > 12 else display
                clean_names.append(display)
            bc.categoryAxis.categoryNames = clean_names
            
            bc.bars[0].fillColor = C_ACCENT
            bc.valueAxis.valueMin = 0
            bc.categoryAxis.labels.fontSize = 7
            bc.categoryAxis.labels.fontName = 'Helvetica'
            bc.valueAxis.labels.fontSize = 7
            
            bar_drawing.add(bc)
        else:
            bar_drawing.add(String(50, 75, "No data available", fontSize=10, fillColor=C_TEXT_SEC))
            
        layout_table = Table([[user_table, bar_drawing]], colWidths=[user_table_width, chart_width], hAlign='LEFT')
        layout_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        elems.append(layout_table)
    elems.append(KeepTogether([Spacer(1, 24)]))

    # AI Executive Summary
    elems.append(KeepTogether([Paragraph("AI Executive Summary", S['section'])]))
    summary_text = format_ai_summary(analysis.get_ai_summary())
    if summary_text:
        summary_table = Table(
            [[Paragraph(summary_text, S['callout_body'])]],
            colWidths=[usable_width]
        )
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fbfbfd')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d2d2d7')),
            ('LEFTPADDING', (0, 0), (-1, -1), 16),
            ('RIGHTPADDING', (0, 0), (-1, -1), 16),
            ('TOPPADDING', (0, 0), (-1, -1), 14),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ]))
        elems.append(KeepTogether([summary_table, Spacer(1, 8), Paragraph("Generated by local LLM analysis.", S['caption'])]))
    else:
        elems.append(Paragraph("AI summary not available for this run.", S['body_sm']))
    elems.append(Spacer(1, 32))

    # Issues Table (top 100)
    elems.append(Paragraph("Detected Issues (Top 100)", S['section']))
    if not issues:
        elems.append(Paragraph("✓ No issues found. Excellent work!", S['body']))
    else:
        issue_header = [['#', 'Severity', 'Family', 'File', 'Line']]
        issue_rows = []
        for idx, issue in enumerate(issues[:100], 1):
            file_name = issue.get('file_path', '')
            parts = file_name.replace('\\', '/').split('/')
            file_display = '/'.join(parts[-3:]) if len(parts) > 2 else file_name
            if len(file_display) > 42:
                file_display = '…' + file_display[-40:]
            
            issue_type = issue.get('defect_family', 'unknown')
            if len(issue_type) > 24:
                issue_type = issue_type[:22] + '…'
            
            sev = issue.get('severity', 'info')
            issue_rows.append([str(idx), sev.upper(), issue_type, file_display, str(issue.get('line_number', '?'))])

        # Width logic: 5% ID, 15% Severity, 30% Family, 40% File, 10% Line
        issue_table = Table(
            issue_header + issue_rows,
            colWidths=[
                usable_width * 0.05,
                usable_width * 0.15,
                usable_width * 0.28,
                usable_width * 0.42,
                usable_width * 0.10
            ],
            hAlign='LEFT', repeatRows=1,
        )
        issue_style = [
            ('BACKGROUND', (0, 0), (-1, 0), C_LIGHT_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), C_TEXT_SEC),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'LEFT'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'), # ID
            ('ALIGN', (1, 0), (1, -1), 'CENTER'), # Severity
            ('ALIGN', (-1, 0), (-1, -1), 'CENTER'), # Line
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('FONTNAME', (3, 1), (3, -1), 'Courier'),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#f5f5f7')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]
        
        sev_c_map = {
            'BLOCKER': C_BLOCKER,
            'CRITICAL': C_CRITICAL,
            'HIGH': C_HIGH,
            'MEDIUM': colors.HexColor('#d97706'),
            'LOW': C_LOW,
            'INFO': C_TEXT_MUT,
            'TRACE': C_TEXT_MUT,
        }
        for row_i, issue in enumerate(issues[:100], 1):
            sev = issue.get('severity', 'info').upper()
            issue_style.append(('TEXTCOLOR', (1, row_i), (1, row_i), sev_c_map.get(sev, C_TEXT_MUT)))
            issue_style.append(('FONTNAME', (1, row_i), (1, row_i), 'Helvetica-Bold'))
        issue_table.setStyle(TableStyle(issue_style))
        elems.append(issue_table)
        if len(issues) > 100:
            elems.append(Spacer(1, 8))
            elems.append(Paragraph(f"<i>… and {len(issues) - 100} more issues not shown.</i>", S['caption']))

    elems.append(Spacer(1, 32))
    elems.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e5e7eb')))
    elems.append(Spacer(1, 8))
    elems.append(Paragraph(
        f"This report was generated by CodeAutopsy AI v2.0. "
        f"Repository: <b>{repo_name}</b>  •  Analysis ID: {analysis_id[:8]}",
        S['caption']
    ))

    doc.build(elems, canvasmaker=canvas_maker)

    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="codeautopsy_{repo_name.replace("/", "_")}.pdf"'
        },
    )
