"""
Report Generator API Route
===========================
Exports analysis results as JSON or formatted PDF files.
"""

import json
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from app.database import get_db, AnalysisResult

router = APIRouter(prefix="/api/report", tags=["Report"])


@router.get("/{analysis_id}/json")
async def export_json(analysis_id: str, db: Session = Depends(get_db)):
    """Export the full analysis result as a JSON file."""
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    if analysis.status != "complete":
        raise HTTPException(status_code=400, detail="Analysis is not yet complete")

    issues = analysis.get_issues()
    
    # Calculate severity summary
    sev_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for i in issues:
        s = i.get("severity", "info")
        if s in sev_summary:
            sev_summary[s] += 1
        else:
            sev_summary[s] = 1

    # Get iso format string for date
    if analysis.completed_at:
        analyzed_at = analysis.completed_at.isoformat()
    elif analysis.created_at:
        analyzed_at = analysis.created_at.isoformat()
    else:
        analyzed_at = datetime.utcnow().isoformat()

    # Format the data for export
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
        headers={
            "Content-Disposition": f'attachment; filename="codeautopsy_report_{analysis_id[:8]}.json"'
        }
    )


@router.get("/{analysis_id}/pdf")
async def export_pdf(analysis_id: str, db: Session = Depends(get_db)):
    """Export the analysis result as a formatted PDF report."""
    analysis = db.query(AnalysisResult).filter(AnalysisResult.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    if analysis.status != "complete":
        raise HTTPException(status_code=400, detail="Analysis is not yet complete")

    issues = analysis.get_issues()
    
    # Sort issues by severity (critical -> high -> medium -> low -> info)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 99))

    # Generate PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#4338ca'), # Indigo 700
        spaceAfter=20
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#4b5563'),
        spaceAfter=30
    )
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1f2937'),
        spaceBefore=20,
        spaceAfter=10
    )
    
    elements = []
    
    # Title Page
    repo_name = analysis.repo_url.split('github.com/')[-1].strip('/')
    elements.append(Paragraph("CodeAutopsy Analysis Report", title_style))
    if analysis.completed_at:
        date_str = analysis.completed_at.strftime("%B %d, %Y %H:%M UTC")
    elif analysis.created_at:
        date_str = analysis.created_at.strftime("%B %d, %Y %H:%M UTC")
    else:
        date_str = datetime.utcnow().strftime("%B %d, %Y %H:%M UTC")
        
    elements.append(Paragraph(f"Repository: <b>{repo_name}</b><br/>Date: {date_str}", subtitle_style))
    
    # Executive Summary
    elements.append(Paragraph("Executive Summary", heading_style))
    health_score = analysis.health_score or 0
    score_color = "#10b981" if health_score >= 80 else ("#f59e0b" if health_score >= 60 else "#ef4444")
    
    summary_data = [
        ["Health Score", "Total Issues", "Files Analyzed"],
        [f"{health_score}/100", str(len(issues)), str(analysis.file_count or 0)]
    ]
    
    t = Table(summary_data, colWidths=[2*inch, 2*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor('#374151')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('TEXTCOLOR', (0,1), (0,1), colors.HexColor(score_color)),
        ('FONTNAME', (0,1), (0,1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,1), 14),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))
    
    # Severity Breakdown
    sev_data = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for i in issues:
        s = i.get("severity", "info")
        if s in sev_data:
            sev_data[s] += 1
        else:
            sev_data[s] = 1
            
    elements.append(Paragraph("Issue Breakdown by Severity", heading_style))
    
    breakdown_data = [["Critical", "High", "Medium", "Low", "Info"],
                     [str(sev_data.get('critical', 0)), 
                      str(sev_data.get('high', 0)), 
                      str(sev_data.get('medium', 0)), 
                      str(sev_data.get('low', 0)), 
                      str(sev_data.get('info', 0))]]
                      
    t2 = Table(breakdown_data, colWidths=[1.2*inch]*5)
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#f3f4f6')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0,0), (0,0), colors.HexColor('#991b1b')), # Critical
        ('TEXTCOLOR', (1,0), (1,0), colors.HexColor('#c2410c')), # High
        ('TEXTCOLOR', (2,0), (2,0), colors.HexColor('#b45309')), # Medium
        ('TEXTCOLOR', (3,0), (3,0), colors.HexColor('#1d4ed8')), # Low
        ('TEXTCOLOR', (4,0), (4,0), colors.HexColor('#4b5563')), # Info
        ('FONTSIZE', (0,1), (-1,1), 12),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e5e7eb')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 30))
    
    # Detailed Issues List
    elements.append(Paragraph("Detected Issues", heading_style))
    
    if not issues:
        elements.append(Paragraph("No issues found in this repository. Excellent work!", styles['Normal']))
    else:
        # Create a table for the issues
        issue_table_data = [["Severity", "Type", "File", "Line"]]
        
        for issue in issues[:100]:  # Limit to 100 to avoid massive PDFs
            file_name = issue.get('file_path', '').split('/')[-1]
            if len(file_name) > 30:
                file_name = "..." + file_name[-27:]
                
            issue_table_data.append([
                issue.get('severity', 'info').upper(),
                issue.get('issue_type', 'unknown'),
                file_name,
                str(issue.get('line_number', '?'))
            ])
            
        t3 = Table(issue_table_data, colWidths=[1*inch, 2.5*inch, 2.5*inch, 0.8*inch])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4f46e5')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (0,-1), 'CENTER'), # Severity & Line center
            ('ALIGN', (-1,0), (-1,-1), 'CENTER'), 
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            # Row alternation coloring
            *[('BACKGROUND', (0,i), (-1,i), colors.HexColor('#f9fafb')) for i in range(1, len(issue_table_data), 2)]
        ]))
        elements.append(t3)
        
        if len(issues) > 100:
            elements.append(Spacer(1, 10))
            elements.append(Paragraph(f"<i>... and {len(issues) - 100} more issues not shown in this summary.</i>", styles['Normal']))

    # Build PDF
    doc.build(elements)
    
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="codeautopsy_report_{repo_name.replace("/", "_")}.pdf"'
        }
    )
