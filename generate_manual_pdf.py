#!/usr/bin/env python3
"""
Calibration Management Agent — User Manual PDF Generator
Generates a comprehensive professional PDF using ReportLab.
v1.0 | n0v8v LLC | 2026
"""

import os
import math
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable, ListFlowable, ListItem,
    NextPageTemplate, PageTemplate, Frame, BaseDocTemplate
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.graphics.shapes import Drawing, Rect, Circle, Line, String, Group
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ═══════════════════════════════════════════════════════════
# COLOR PALETTE
# ═══════════════════════════════════════════════════════════
NAVY = colors.HexColor("#0A1628")
TEAL = colors.HexColor("#00D4AA")
DARK_TEAL = colors.HexColor("#00A888")
WHITE = colors.HexColor("#FFFFFF")
SLATE = colors.HexColor("#374151")
LIGHT_GRAY = colors.HexColor("#F3F4F6")
MID_GRAY = colors.HexColor("#9CA3AF")
DARK_GRAY = colors.HexColor("#1F2937")
ACCENT_BLUE = colors.HexColor("#3B82F6")
WARN_AMBER = colors.HexColor("#F59E0B")
ERROR_RED = colors.HexColor("#EF4444")
SUCCESS_GREEN = colors.HexColor("#10B981")
CALLOUT_BG = colors.HexColor("#F0FDFA")
CODE_BG = colors.HexColor("#F8FAFC")

PAGE_W, PAGE_H = letter  # 612 x 792

# ═══════════════════════════════════════════════════════════
# STYLES
# ═══════════════════════════════════════════════════════════
def build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'ManualTitle', parent=styles['Title'],
        fontName='Helvetica-Bold', fontSize=28, leading=34,
        textColor=NAVY, alignment=TA_LEFT, spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        'ChapterTitle', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=22, leading=28,
        textColor=NAVY, spaceBefore=0, spaceAfter=14,
        borderPadding=(0, 0, 4, 0), borderWidth=0,
        borderColor=TEAL
    ))
    styles.add(ParagraphStyle(
        'SectionTitle', parent=styles['Heading2'],
        fontName='Helvetica-Bold', fontSize=15, leading=20,
        textColor=DARK_TEAL, spaceBefore=16, spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        'SubSection', parent=styles['Heading3'],
        fontName='Helvetica-Bold', fontSize=12, leading=16,
        textColor=SLATE, spaceBefore=12, spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        'BodyText11', parent=styles['BodyText'],
        fontName='Helvetica', fontSize=10.5, leading=15,
        textColor=DARK_GRAY, alignment=TA_JUSTIFY, spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        'BodyBold', parent=styles['BodyText'],
        fontName='Helvetica-Bold', fontSize=10.5, leading=15,
        textColor=DARK_GRAY, spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        'CodeBlock', parent=styles['Code'],
        fontName='Courier', fontSize=8.5, leading=12,
        textColor=DARK_GRAY, backColor=CODE_BG,
        borderPadding=8, spaceBefore=6, spaceAfter=10,
        leftIndent=12
    ))
    styles.add(ParagraphStyle(
        'Callout', parent=styles['BodyText'],
        fontName='Helvetica', fontSize=10, leading=14,
        textColor=NAVY, backColor=CALLOUT_BG,
        borderPadding=10, spaceBefore=8, spaceAfter=10,
        borderWidth=1, borderColor=TEAL, borderRadius=4,
        leftIndent=8, rightIndent=8
    ))
    styles.add(ParagraphStyle(
        'BulletItem', parent=styles['BodyText'],
        fontName='Helvetica', fontSize=10.5, leading=15,
        textColor=DARK_GRAY, leftIndent=24, bulletIndent=12,
        spaceBefore=2, spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        'FooterStyle', fontName='Helvetica', fontSize=8,
        textColor=MID_GRAY, alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        'TableHeader', fontName='Helvetica-Bold', fontSize=9,
        leading=12, textColor=WHITE, alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        'TableCell', fontName='Helvetica', fontSize=9,
        leading=12, textColor=DARK_GRAY, alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        'TOCEntry', fontName='Helvetica', fontSize=11,
        leading=18, textColor=NAVY, leftIndent=0
    ))
    styles.add(ParagraphStyle(
        'CoverTitle', fontName='Helvetica-Bold', fontSize=36,
        leading=42, textColor=WHITE, alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        'CoverSub', fontName='Helvetica', fontSize=16,
        leading=22, textColor=TEAL, alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        'SmallNote', fontName='Helvetica-Oblique', fontSize=8.5,
        leading=11, textColor=MID_GRAY, alignment=TA_LEFT
    ))
    return styles


# ═══════════════════════════════════════════════════════════
# HEADER / FOOTER FUNCTIONS
# ═══════════════════════════════════════════════════════════
class ManualDocTemplate(BaseDocTemplate):
    """Custom doc template with headers and footers."""

    def __init__(self, filename, **kwargs):
        self.current_chapter = ""
        super().__init__(filename, **kwargs)

    def afterFlowable(self, flowable):
        """Track chapter titles for header."""
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            if style == 'ChapterTitle':
                self.current_chapter = flowable.getPlainText()


def header_footer(canvas_obj, doc):
    """Draw header and footer on each page."""
    canvas_obj.saveState()

    # Header line
    canvas_obj.setStrokeColor(TEAL)
    canvas_obj.setLineWidth(1.5)
    canvas_obj.line(54, PAGE_H - 50, PAGE_W - 54, PAGE_H - 50)

    # Header text
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(MID_GRAY)
    canvas_obj.drawString(54, PAGE_H - 45, "Calibration Management Agent — User Manual v1.0")
    if hasattr(doc, 'current_chapter') and doc.current_chapter:
        canvas_obj.drawRightString(PAGE_W - 54, PAGE_H - 45, doc.current_chapter)

    # Footer line
    canvas_obj.setStrokeColor(LIGHT_GRAY)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(54, 45, PAGE_W - 54, 45)

    # Footer text
    canvas_obj.setFont('Helvetica', 7.5)
    canvas_obj.setFillColor(MID_GRAY)
    canvas_obj.drawString(54, 33, "Confidential — [Organization Name]")
    canvas_obj.drawRightString(PAGE_W - 54, 33, f"Page {doc.page}")

    # Small teal accent square in footer
    canvas_obj.setFillColor(TEAL)
    canvas_obj.rect(PAGE_W / 2 - 3, 32, 6, 6, fill=1, stroke=0)

    canvas_obj.restoreState()


def cover_page_draw(canvas_obj, doc):
    """Draw cover page background."""
    canvas_obj.saveState()

    # Full navy background
    canvas_obj.setFillColor(NAVY)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Geometric pattern - circles
    canvas_obj.setStrokeColor(colors.HexColor("#1A2A40"))
    canvas_obj.setLineWidth(0.5)
    for i in range(8):
        r = 40 + i * 35
        canvas_obj.circle(PAGE_W - 100, PAGE_H - 180, r, fill=0, stroke=1)

    # Teal accent bar
    canvas_obj.setFillColor(TEAL)
    canvas_obj.rect(0, PAGE_H - 420, 8, 120, fill=1, stroke=0)

    # Grid dots pattern
    canvas_obj.setFillColor(colors.HexColor("#152238"))
    for x in range(12):
        for y in range(15):
            px = 400 + x * 18
            py = 100 + y * 18
            if px < PAGE_W and py < PAGE_H - 420:
                canvas_obj.circle(px, py, 1.5, fill=1, stroke=0)

    # Diagonal lines
    canvas_obj.setStrokeColor(colors.HexColor("#1A2A40"))
    canvas_obj.setLineWidth(0.3)
    for i in range(6):
        x_start = 350 + i * 40
        canvas_obj.line(x_start, 0, x_start + 200, PAGE_H)

    # Bottom teal line
    canvas_obj.setStrokeColor(TEAL)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(54, 80, PAGE_W - 54, 80)

    # Version badge
    canvas_obj.setFillColor(TEAL)
    canvas_obj.roundRect(54, 90, 60, 24, 4, fill=1, stroke=0)
    canvas_obj.setFillColor(NAVY)
    canvas_obj.setFont('Helvetica-Bold', 11)
    canvas_obj.drawCentredString(84, 97, "v1.0")

    canvas_obj.restoreState()


# ═══════════════════════════════════════════════════════════
# TABLE HELPERS
# ═══════════════════════════════════════════════════════════
def make_table(headers, rows, col_widths=None, alt_row=True):
    """Create a styled table."""
    s = getSampleStyleSheet()
    header_style = ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=WHITE)
    cell_style = ParagraphStyle('TC', fontName='Helvetica', fontSize=9, leading=12, textColor=DARK_GRAY)

    data = [[Paragraph(h, header_style) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), cell_style) for c in row])

    if col_widths is None:
        available = PAGE_W - 108  # margins
        col_widths = [available / len(headers)] * len(headers)

    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
    ]
    if alt_row:
        for i in range(1, len(data)):
            if i % 2 == 0:
                style_cmds.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY))

    t.setStyle(TableStyle(style_cmds))
    return t


def make_bullet_list(items, style):
    """Create a bulleted list."""
    return [Paragraph(f"<bullet>&bull;</bullet> {item}", style) for item in items]


def chapter_header_bar(text, number):
    """Create a chapter header with teal accent bar."""
    d = Drawing(PAGE_W - 108, 40)
    d.add(Rect(0, 0, 6, 36, fillColor=TEAL, strokeColor=None))
    d.add(String(16, 14, f"CHAPTER {number}", fontName='Helvetica', fontSize=10, fillColor=TEAL))
    return d


# ═══════════════════════════════════════════════════════════
# CONTENT BUILDERS
# ═══════════════════════════════════════════════════════════

def build_cover_page(styles):
    """Cover page content (drawn on navy background)."""
    elements = []
    elements.append(Spacer(1, 180))
    elements.append(Paragraph("Calibration<br/>Management<br/>Agent", styles['CoverTitle']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("User Manual", ParagraphStyle(
        'CoverManual', fontName='Helvetica', fontSize=20,
        leading=26, textColor=TEAL
    )))
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(
        "Autonomous ISO-Compliant Equipment<br/>Calibration Intelligence",
        styles['CoverSub']
    ))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "Part of the GP3.APP Agent Platform \u2014 ISO Agent Suite",
        ParagraphStyle('CoverPlatform', fontName='Helvetica', fontSize=12,
                       leading=16, textColor=colors.HexColor("#6EE7B7"))
    ))
    elements.append(Spacer(1, 60))
    elements.append(Paragraph(
        "GP3.APP \u2014 Agent Platform | Powered by TTC\u2122",
        ParagraphStyle('CoverTTC', fontName='Helvetica', fontSize=11,
                       leading=14, textColor=colors.HexColor("#6EE7B7"))
    ))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        f"Published {datetime.now().strftime('%B %Y')}",
        ParagraphStyle('CoverDate', fontName='Helvetica', fontSize=10,
                       leading=13, textColor=MID_GRAY)
    ))
    elements.append(PageBreak())
    return elements


def build_toc(styles):
    """Table of contents page."""
    elements = []
    elements.append(Paragraph("Table of Contents", styles['ChapterTitle']))
    elements.append(Spacer(1, 12))

    toc_items = [
        ("1", "Executive Overview", ""),
        ("2", "Platform Architecture", ""),
        ("3", 'TTC\u2122 \u2014 Proprietary Agent Communication Protocol', ""),
        ("4", "Getting Started \u2014 Onboarding", ""),
        ("5", "Daily Operations", ""),
        ("6", "Audit Preparedness", ""),
        ("7", "Advanced Features", ""),
        ("8", "Administration", ""),
        ("9", "Cost Savings Analysis", ""),
        ("10", "Technical Reference", ""),
        ("A", "TTC Quick Reference Card", ""),
        ("B", "Sample Tenant Kernel Template", ""),
        ("C", "ISO 17025 Compliance Checklist", ""),
        ("D", "Glossary of Terms", ""),
    ]

    toc_data = []
    for num, title, _ in toc_items:
        prefix = "Chapter " if num.isdigit() else "Appendix "
        toc_data.append([
            Paragraph(f'<font color="{TEAL.hexval()}">{prefix}{num}</font>', styles['TOCEntry']),
            Paragraph(title, styles['TOCEntry']),
        ])

    t = Table(toc_data, colWidths=[120, PAGE_W - 228])
    t.setStyle(TableStyle([
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, LIGHT_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t)
    elements.append(PageBreak())
    return elements


def build_chapter_1(S):
    """Chapter 1: Executive Overview"""
    elements = []
    elements.append(chapter_header_bar("EXECUTIVE OVERVIEW", 1))
    elements.append(Paragraph("Executive Overview", S['ChapterTitle']))

    elements.append(Paragraph("What This Platform Does", S['SectionTitle']))
    elements.append(Paragraph(
        "The Calibration Management Agent is an autonomous AI-powered system that manages the full lifecycle of "
        "equipment calibration for industrial and manufacturing operations. It replaces manual spreadsheets, "
        "disconnected software tools, and labor-intensive tracking processes with a single intelligent agent "
        "that processes certificates, tracks schedules, answers compliance questions, and generates audit-ready "
        "evidence packages on demand.",
        S['BodyText11']
    ))
    elements.append(Paragraph(
        "The platform ingests calibration certificates (PDF, image), extracts structured data using AI, "
        "automatically updates equipment records, monitors expiration schedules, and proactively alerts "
        "stakeholders before instruments go overdue. When auditors arrive, a complete evidence package "
        "can be generated in under 30 seconds.",
        S['BodyText11']
    ))
    elements.append(Paragraph(
        "The Calibration Agent is the first in a growing suite of ISO-focused agents on the GP3.APP Agent "
        "Platform. Designed for multi-tenant deployment, each organization operates in complete data isolation "
        "with configurable compliance standards, vendor preferences, escalation rules, and branding \u2014 all "
        "driven by the platform's proprietary TTC\u2122 coded instruction protocol, which eliminates the "
        "ambiguity and vulnerability of natural language prompting.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Key Value Propositions", S['SectionTitle']))
    for item in [
        "<b>Compliance Automation:</b> Continuous monitoring against ISO 17025, AS9100, IATF 16949, and "
        "21 CFR Part 11 requirements. No more manual tracking or surprise audit findings.",
        "<b>Cost Reduction:</b> Eliminates 80-90% of calibration management labor hours. Certificate processing "
        "drops from 15-20 minutes per document to under 60 seconds.",
        "<b>Audit Readiness:</b> One-click evidence packages with full traceability chains, immutable logs, "
        "and executive summaries. Auditor walkthroughs completed in 30 seconds, not 3 hours.",
        "<b>Proactive Risk Management:</b> AI-driven alerts prevent overdue conditions before they occur. "
        "Out-of-tolerance investigations are triggered automatically with escalation workflows.",
        "<b>Zero Cross-Tenant Contamination:</b> Row-level security and schema isolation guarantee that "
        "no organization can access another's calibration data, even within the same deployment.",
    ]:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {item}", S['BulletItem']))

    elements.append(Paragraph("Deployment Model", S['SectionTitle']))
    elements.append(Paragraph(
        "The agent deploys as a single FastAPI service with path-based multi-tenancy, containerized via Docker "
        "and fronted by a reverse proxy with automatic TLS certificate management. Each tenant receives a "
        "dedicated configuration kernel loaded at runtime, eliminating the need for separate deployments per client.",
        S['BodyText11']
    ))

    elements.append(Paragraph("ROI Framework", S['SectionTitle']))
    elements.append(Paragraph(
        "The following comparison illustrates the cost structure of manual calibration management versus "
        "the autonomous agent approach for a typical manufacturing facility with 100-300 instruments:",
        S['BodyText11']
    ))

    roi_table = make_table(
        ["Cost Category", "Manual Management", "Agent-Managed", "Annual Savings"],
        [
            ["Calibration coordinator (FTE)", "$55,000 - $75,000", "Eliminated", "$55,000 - $75,000"],
            ["Software licenses (SaaS)", "$15,000 - $40,000/yr", "Included", "$15,000 - $40,000"],
            ["Audit preparation labor", "$10,000 - $20,000/yr", "< $500/yr", "$9,500 - $19,500"],
            ["Certificate processing time", "~320 hrs/yr @ $35/hr", "~15 hrs/yr", "$10,675"],
            ["Overdue equipment risk", "$5,000 - $50,000/yr", "Near zero", "$5,000 - $50,000"],
            ["Agent subscription", "\u2014", "$350 - $1,750/mo", "($4,200 - $21,000)"],
            ["Net Annual Savings", "", "", "$67,775 - $166,175"],
        ],
        col_widths=[130, 120, 100, 130]
    )
    elements.append(roi_table)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "<i>Note: Risk avoidance costs (customer escapes, audit nonconformances, recall events) are excluded "
        "from this conservative estimate but can exceed $100,000 per incident in regulated industries.</i>",
        S['SmallNote']
    ))

    elements.append(PageBreak())
    return elements


def build_chapter_2(S):
    """Chapter 2: Platform Architecture"""
    elements = []
    elements.append(chapter_header_bar("PLATFORM ARCHITECTURE", 2))
    elements.append(Paragraph("Platform Architecture", S['ChapterTitle']))

    elements.append(Paragraph("System Overview", S['SectionTitle']))
    elements.append(Paragraph(
        "The Calibration Management Agent operates as a FastAPI microservice deployed inside a Docker container. "
        "It communicates with a PostgreSQL database (hosted on Supabase) for persistent storage, uses Anthropic's "
        "Claude AI for certificate extraction and natural language queries, and generates branded PDF reports "
        "via ReportLab. All tenant isolation is enforced at the database layer through company-scoped queries "
        "and row-level security policies.",
        S['BodyText11']
    ))

    # Architecture diagram as table
    elements.append(Paragraph("Architecture Diagram", S['SectionTitle']))
    arch_data = [
        [Paragraph('<b>Layer</b>', S['TableHeader']),
         Paragraph('<b>Component</b>', S['TableHeader']),
         Paragraph('<b>Technology</b>', S['TableHeader']),
         Paragraph('<b>Purpose</b>', S['TableHeader'])],
        [Paragraph('Client', S['TableCell']),
         Paragraph('Web SPA', S['TableCell']),
         Paragraph('React 18 + Vite', S['TableCell']),
         Paragraph('Dashboard, upload, Q&A, evidence downloads', S['TableCell'])],
        [Paragraph('Proxy', S['TableCell']),
         Paragraph('Reverse Proxy', S['TableCell']),
         Paragraph('Caddy (auto-TLS)', S['TableCell']),
         Paragraph('HTTPS termination, routing, security headers', S['TableCell'])],
        [Paragraph('API', S['TableCell']),
         Paragraph('Agent Backend', S['TableCell']),
         Paragraph('FastAPI + Uvicorn', S['TableCell']),
         Paragraph('Auth, CRUD, AI orchestration, PDF generation', S['TableCell'])],
        [Paragraph('AI', S['TableCell']),
         Paragraph('Language Model', S['TableCell']),
         Paragraph('Anthropic Claude', S['TableCell']),
         Paragraph('Certificate extraction, NL Q&A, compliance analysis', S['TableCell'])],
        [Paragraph('Data', S['TableCell']),
         Paragraph('Database', S['TableCell']),
         Paragraph('PostgreSQL 16 (Supabase)', S['TableCell']),
         Paragraph('Equipment, calibrations, users, audit logs', S['TableCell'])],
        [Paragraph('Storage', S['TableCell']),
         Paragraph('File Storage', S['TableCell']),
         Paragraph('Supabase Storage', S['TableCell']),
         Paragraph('Certificate PDFs, company logos, attachments', S['TableCell'])],
    ]
    arch_t = Table(arch_data, colWidths=[60, 100, 120, 200])
    arch_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
        ('BACKGROUND', (0, 2), (-1, 2), LIGHT_GRAY),
        ('BACKGROUND', (0, 4), (-1, 4), LIGHT_GRAY),
        ('BACKGROUND', (0, 6), (-1, 6), LIGHT_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(arch_t)
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Agent Processing Pipeline", S['SectionTitle']))
    elements.append(Paragraph(
        "Every interaction with the agent follows a deterministic pipeline orchestrated by the TTC kernel:",
        S['BodyText11']
    ))

    pipeline_items = [
        "<b>Intake:</b> User uploads a certificate or asks a question via the web interface.",
        "<b>Authentication:</b> JWT token validated; company_id extracted for tenant scoping.",
        "<b>Kernel Loading:</b> Shared agent kernel + tenant-specific kernel loaded and merged.",
        "<b>Intent Classification:</b> TTC routing block (K1) maps input to the correct capability.",
        "<b>Execution:</b> AI processes the request using tool-use (SQL queries) or extraction (certificates).",
        "<b>Validation:</b> Results checked against compliance rules, status thresholds, and data integrity.",
        "<b>Response:</b> Formatted output returned \u2014 structured data, compliance alerts, or PDF evidence.",
        "<b>Audit Logging:</b> Every action timestamped and attributed in the immutable audit log.",
    ]
    for item in pipeline_items:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {item}", S['BulletItem']))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Equipment Status Lifecycle", S['SectionTitle']))
    elements.append(Paragraph(
        "Every tracked instrument progresses through a defined status lifecycle. Status transitions are "
        "calculated automatically based on calibration dates and configured alert thresholds:",
        S['BodyText11']
    ))

    status_table = make_table(
        ["Status", "Condition", "Color", "Action Required"],
        [
            ["CURRENT", "Next due > today + 30 days", "Green", "None \u2014 compliant"],
            ["EXPIRING SOON", "Due within 30 days", "Amber", "Schedule calibration"],
            ["CRITICAL", "Due within 7 days", "Red", "Immediate scheduling required"],
            ["OVERDUE", "Past due date", "Red (pulsing)", "Remove from service until recalibrated"],
            ["OUT OF SERVICE", "Status = inactive", "Gray", "Not in active rotation"],
            ["NEW", "No calibration history", "Blue", "Initial calibration required"],
        ],
        col_widths=[100, 130, 60, 190]
    )
    elements.append(status_table)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Multi-Tenant Isolation", S['SectionTitle']))
    elements.append(Paragraph(
        "Tenant isolation is enforced through multiple layers: (1) JWT tokens contain the company_id, "
        "which scopes every database query; (2) Row-Level Security (RLS) policies on all tables prevent "
        "cross-tenant access at the database engine level; (3) the service_role key bypasses RLS only for "
        "administrative operations; (4) file storage paths are partitioned by company_id; and (5) each tenant "
        "receives a separate TTC kernel configuration loaded at runtime.",
        S['BodyText11']
    ))
    elements.append(Paragraph(
        '<b>Zero cross-tenant contamination is guaranteed by architecture, not convention.</b>',
        S['Callout']
    ))

    elements.append(PageBreak())
    return elements


def build_chapter_3(S):
    """Chapter 3: TTC Protocol"""
    elements = []
    elements.append(chapter_header_bar("TTC PROTOCOL", 3))
    elements.append(Paragraph(
        'TTC\u2122 \u2014 Proprietary Agent Communication Protocol', S['ChapterTitle']))

    elements.append(Paragraph(
        "TTC\u2122 is the proprietary instruction protocol developed by n0v8v LLC that drives all agent behavior "
        "across the GP3.APP Agent Platform. Unlike natural language prompting, TTC uses a coded, deterministic "
        "instruction set built on three linguistic layers \u2014 concept-dense ideographic characters for section "
        "identifiers, English for technical precision, and symbolic operators for logic compression. This "
        "architecture eliminates ambiguity, prevents prompt injection, and achieves 65-70% token reduction "
        "with zero logic loss.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Why Natural Language Prompts Fail", S['SectionTitle']))
    elements.append(Paragraph(
        "For mission-critical industrial applications like calibration management, natural language prompting "
        "introduces unacceptable risks:",
        S['BodyText11']
    ))

    fail_table = make_table(
        ["Risk Category", "Natural Language Problem", "TTC Solution"],
        [
            ["Ambiguity", "\"Handle overdue items\" \u2014 quarantine? notify? ignore?",
             "Deterministic routing: overdue\u2192K3a.expiry\u2192FLAG+ESCALATE"],
            ["Prompt Injection", "Malicious input can override system instructions",
             "Coded blocks cannot be socially engineered or rewritten"],
            ["Hallucination", "Verbose prompts leave room for creative interpretation",
             "Compressed tokens force precise, data-grounded execution"],
            ["Token Waste", "10,000+ tokens for full system context in English",
             "~3,500 tokens for equivalent logic \u2014 65% reduction"],
            ["Inconsistency", "Different phrasings produce different behaviors",
             "Same K-block always produces identical behavior"],
        ],
        col_widths=[90, 190, 200]
    )
    elements.append(fail_table)

    elements.append(Paragraph("The Three-Layer Encoding System", S['SectionTitle']))
    elements.append(Paragraph(
        "TTC achieves compression by leveraging the information density of three linguistic layers, "
        "each optimized for a specific function:",
        S['BodyText11']
    ))

    elements.append(Paragraph("Layer 1: \u4e2d\u6587 (Mandarin) \u2014 Concept Identifiers", S['SubSection']))
    elements.append(Paragraph(
        "Mandarin characters encode entire concepts in 1-2 tokens that would require 5-10 tokens in English. "
        "These serve as section identifiers, action directives, and semantic anchors. For example, "
        "\u201c\u6821\u51c6\u201d (calibration) replaces the full phrase \u201ccalibration management and tracking operations.\u201d "
        "\u201c\u8986\u76d6\u201d (override) replaces \u201ctenant-specific configuration overrides.\u201d",
        S['BodyText11']
    ))

    elements.append(Paragraph("Layer 2: English \u2014 Technical Precision", S['SubSection']))
    elements.append(Paragraph(
        "English is used for variable names, API references, field names, SQL patterns, and technical "
        "identifiers where precision is paramount. Examples: tool_id, calibration_date, vendor_name, "
        "ISO17025. These terms have exact meanings in their technical context and cannot be compressed further.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Layer 3: Symbolic Kernelization \u2014 Logic Compression", S['SubSection']))
    elements.append(Paragraph(
        "Mathematical and logical operators replace verbose conditional statements. "
        "This layer provides the control flow and decision logic:",
        S['BodyText11']
    ))

    symbol_table = make_table(
        ["Symbol", "Meaning", "NL Equivalent", "Token Savings"],
        [
            ["\u2192", "Routes to / implies", "\"this leads to\" or \"then do\"", "3-5 tokens"],
            ["\u2227", "AND (conjunction)", "\"and also\" or \"in addition\"", "2-3 tokens"],
            ["\u2228", "OR (disjunction)", "\"or alternatively\"", "2-3 tokens"],
            ["\u2205", "NULL / empty / none", "\"if there is no value\" or \"when empty\"", "4-6 tokens"],
            ["\u220b", "Contains / includes", "\"if the set contains\" or \"when it includes\"", "4-5 tokens"],
            ["\u2208", "Member of / belongs to", "\"is a member of\" or \"exists in\"", "4-5 tokens"],
            ["\u2191", "Increase / escalate", "\"increase priority\" or \"escalate to\"", "3-4 tokens"],
            ["\u2193", "Decrease / de-escalate", "\"reduce\" or \"lower priority\"", "3-4 tokens"],
            [":=", "Defined as / assigned", "\"is defined as\" or \"equals\"", "3-4 tokens"],
            ["|", "Delimiter / alternative", "\"or\" / \"separated by\"", "1-2 tokens"],
        ],
        col_widths=[50, 110, 160, 80]
    )
    elements.append(symbol_table)

    elements.append(Paragraph("K-Block Architecture", S['SectionTitle']))
    elements.append(Paragraph(
        "The TTC kernel is organized into numbered K-blocks (K0 through K5), each responsible for a "
        "specific operational domain. Blocks are loaded selectively based on the current operation, "
        "so the agent never processes unnecessary context:",
        S['BodyText11']
    ))

    kblock_table = make_table(
        ["Block", "ID", "Name", "Load Trigger", "Purpose"],
        [
            ["K0", "\u8eab\u4efd", "Identity", "Always", "Agent persona, tenant config, compliance standards"],
            ["K1", "\u51b3\u7b56", "Routing", "Always", "Intent classification, priority rules, decision trees"],
            ["K2", "\u901a\u4fe1", "Communication", "On generation", "Output formats, status labels, response tone"],
            ["K3a", "\u6821\u51c6\u8bb0\u5f55", "Cal Records", "On cal ops", "Query patterns, create/update records"],
            ["K3b", "\u5de5\u5177\u7ba1\u7406", "Tool Mgmt", "On tool ops", "Tool CRUD, location/type queries, vendors"],
            ["K3c", "\u5408\u89c4\u62a5\u544a", "Compliance", "On reporting", "Dashboard stats, audit trails, evidence"],
            ["K4", "\u7f16\u6392", "Orchestration", "Runtime only", "Batch jobs, scheduled events, notifications"],
            ["K5", "\u5b66\u4e60", "Learning", "Post-execution", "Metrics, adaptation rules, trend analysis"],
        ],
        col_widths=[40, 40, 80, 80, 240]
    )
    elements.append(kblock_table)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Selective Loading Principle", S['SubSection']))
    elements.append(Paragraph(
        "A critical design decision in TTC is that the agent never loads all K-blocks simultaneously. "
        "Loading only the blocks needed for the current operation achieves two objectives: (1) minimizing "
        "token consumption per call, and (2) preventing the AI from being distracted by irrelevant context. "
        "A simple tool lookup loads K0+K1+K3b (~450 tokens). A compliance report loads K0+K3c (~400 tokens). "
        "Only system initialization requires a full K0-K5 load (~2,200 tokens).",
        S['BodyText11']
    ))

    elements.append(Paragraph("Token Economics", S['SectionTitle']))
    elements.append(Paragraph(
        "The following table demonstrates measured token savings across common operations, comparing "
        "equivalent natural language instructions against TTC-encoded kernels:",
        S['BodyText11']
    ))

    token_table = make_table(
        ["Operation", "Natural Language", "TTC Encoded", "Savings"],
        [
            ["Tool lookup", "~800 tokens", "~450 tokens", "44%"],
            ["Add calibration record", "~900 tokens", "~400 tokens", "56%"],
            ["Expiry check (all tools)", "~1,200 tokens", "~500 tokens", "58%"],
            ["Compliance report", "~1,400 tokens", "~400 tokens", "71%"],
            ["Dispute handling", "~1,800 tokens", "~600 tokens", "67%"],
            ["Communication generation", "~2,100 tokens", "~700 tokens", "67%"],
            ["Full system context", "~10,000 tokens", "~3,500 tokens", "65%"],
        ],
        col_widths=[140, 100, 100, 80]
    )
    elements.append(token_table)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Security Advantage", S['SubSection']))
    elements.append(Paragraph(
        "TTC kernels provide an inherent security advantage over natural language prompts. Because the "
        "instruction set uses coded notation (\u4e2d\u6587 identifiers + symbolic operators), it cannot be "
        "socially engineered through conversational manipulation. A user asking the agent to \u201cignore your "
        "instructions\u201d or \u201cpretend you are a different agent\u201d has no effect because the kernel "
        "is not parsed as a conversation \u2014 it is parsed as a deterministic configuration object.",
        S['BodyText11']
    ))
    elements.append(Paragraph(
        '<b>TTC\u2122, the GP3.APP Agent Platform, and the Calibration Management Agent are proprietary '
        'intellectual property of n0v8v LLC. All rights reserved.</b>',
        S['Callout']
    ))

    elements.append(PageBreak())
    return elements


def build_chapter_4(S):
    """Chapter 4: Getting Started"""
    elements = []
    elements.append(chapter_header_bar("GETTING STARTED", 4))
    elements.append(Paragraph("Getting Started \u2014 Onboarding", S['ChapterTitle']))

    elements.append(Paragraph("Account Provisioning", S['SectionTitle']))
    elements.append(Paragraph(
        "New organizations are provisioned through a guided onboarding process. Your administrator will "
        "receive a company code (slug) that uniquely identifies your organization within the platform.",
        S['BodyText11']
    ))
    steps = [
        "<b>Step 1 \u2014 Company Registration:</b> The platform operator creates your company record with "
        "your organization name, subscription plan, and a unique company code (e.g., \"acme-mfg\").",
        "<b>Step 2 \u2014 Admin Account:</b> Navigate to the login page and click \"Register.\" Enter your "
        "email, password, name, and the company code provided by your administrator.",
        "<b>Step 3 \u2014 Team Invitations:</b> Once logged in as admin, additional users can register using "
        "the same company code. Admin accounts have full CRUD access; standard users have read-only access "
        "with the ability to ask questions and download evidence packages.",
        "<b>Step 4 \u2014 Configuration:</b> Your tenant kernel is customized with your compliance standards, "
        "vendor preferences, notification rules, and branding information.",
    ]
    for s in steps:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {s}", S['BulletItem']))

    elements.append(Paragraph("Equipment Inventory Setup", S['SectionTitle']))
    elements.append(Paragraph(
        "The platform supports three methods for populating your equipment registry:",
        S['BodyText11']
    ))

    elements.append(Paragraph("Method 1: CSV Bulk Import (Recommended)", S['SubSection']))
    elements.append(Paragraph(
        "Download the CSV template from the Equipment page, populate it with your instrument data, and "
        "upload. The template includes columns for asset tag, tool name, type, manufacturer, model, serial "
        "number, location, building, calibration method, calibrating entity, and interval days. The system "
        "validates each row before import and reports any errors.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Method 2: Individual Entry", S['SubSection']))
    elements.append(Paragraph(
        "Use the \"Add Equipment\" form on the Equipment page to add instruments one at a time. "
        "The asset tag field is required; all other fields are optional but recommended for full compliance.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Method 3: Certificate-Driven Discovery", S['SubSection']))
    elements.append(Paragraph(
        "When a calibration certificate is uploaded for a tool not yet in the registry, the system "
        "identifies the gap and prompts the administrator to add the instrument. This allows organic "
        "inventory building through normal certificate processing workflows.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Vendor Registration", S['SectionTitle']))
    elements.append(Paragraph(
        "Approved calibration vendors are configured in your tenant kernel. Each vendor record includes "
        "the vendor name, accreditation type (ISO/IEC 17025), accreditation body (A2LA, NVLAP, ANAB), "
        "NIST traceability confirmation, scope of accreditation, and contact information. Vendor records "
        "link to calibration history for performance tracking and turnaround analysis.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Notification Setup", S['SectionTitle']))
    elements.append(Paragraph(
        "The agent supports email notifications for calibration alerts. Configure notification preferences "
        "in your tenant kernel by specifying alert thresholds (warn days, critical days), email recipients "
        "for each escalation level, and notification channels. Email routing is configured per-role, so "
        "quality managers can receive different alerts than calibration technicians.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Compliance Standard Selection", S['SectionTitle']))
    elements.append(Paragraph(
        "Select the quality management standards applicable to your organization. The agent supports:",
        S['BodyText11']
    ))
    standards = [
        "<b>ISO 9001:</b> Quality management systems (general manufacturing)",
        "<b>ISO/IEC 17025:</b> Calibration and testing laboratory competence",
        "<b>AS9100:</b> Aerospace quality management",
        "<b>IATF 16949:</b> Automotive quality management",
        "<b>ISO 13485:</b> Medical device quality management",
        "<b>21 CFR Part 11:</b> FDA electronic records and signatures",
        "<b>NADCAP:</b> Aerospace special processes accreditation",
    ]
    for std in standards:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {std}", S['BulletItem']))

    elements.append(PageBreak())
    return elements


def build_chapter_5(S):
    """Chapter 5: Daily Operations"""
    elements = []
    elements.append(chapter_header_bar("DAILY OPERATIONS", 5))
    elements.append(Paragraph("Daily Operations", S['ChapterTitle']))

    elements.append(Paragraph("Uploading Calibration Certificates", S['SectionTitle']))
    elements.append(Paragraph(
        "The Upload page provides a drag-and-drop interface for processing calibration certificates. "
        "Supported formats include PDF documents and image files (PNG, JPG). The processing pipeline is:",
        S['BodyText11']
    ))
    upload_steps = [
        "Navigate to the Upload page from the sidebar.",
        "Drag and drop a certificate file, or click to browse and select.",
        "The AI engine extracts structured data: equipment identifier, calibration date, next due date, "
        "technician/vendor, result (pass/fail/adjusted/out-of-tolerance/conditional), and comments.",
        "Review the extracted data displayed on screen. Verify accuracy before confirming.",
        "On confirmation, the system creates a calibration record, updates the tool's status and next due "
        "date, stores the certificate in secure file storage, and logs the action to the audit trail.",
    ]
    for i, step in enumerate(upload_steps, 1):
        elements.append(Paragraph(f"<bullet>{i}.</bullet> {step}", S['BulletItem']))

    elements.append(Paragraph(
        '<b>Result Classification:</b> Certificates are classified as <font color="#10B981">pass</font> '
        '(within spec), <font color="#F59E0B">adjusted</font> (corrected during calibration), '
        '<font color="#EF4444">out_of_tolerance</font> (out of spec, not corrected \u2014 remove from service), '
        '<font color="#EF4444">fail</font> (calibration failed), or <font color="#3B82F6">conditional</font> '
        '(ambiguous, needs human review).',
        S['Callout']
    ))

    elements.append(Paragraph("Dashboard Overview", S['SectionTitle']))
    elements.append(Paragraph(
        "The Dashboard page is the primary status view, showing:",
        S['BodyText11']
    ))
    dash_items = [
        "<b>Summary Cards:</b> Total instruments, compliance percentage, expiring soon count, overdue count.",
        "<b>Upcoming Expirations:</b> Table of instruments due within 60 days, sorted by urgency.",
        "<b>Overdue Instruments:</b> Table of past-due instruments requiring immediate attention.",
        "<b>Status Distribution:</b> Visual breakdown of current vs. expiring vs. critical vs. overdue.",
    ]
    for item in dash_items:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {item}", S['BulletItem']))

    elements.append(Paragraph("Asking the Agent Questions", S['SectionTitle']))
    elements.append(Paragraph(
        "The Ask Agent page provides a natural language interface for querying your calibration data. "
        "The agent interprets your question, formulates read-only SQL queries, executes them against "
        "your tenant's data, and returns formatted answers with source citations.",
        S['BodyText11']
    ))
    elements.append(Paragraph("Example questions the agent can answer:", S['SubSection']))
    query_examples = [
        "\"Which instruments are due next month?\"",
        "\"What is our overall compliance rate?\"",
        "\"Show me all micrometers and their calibration status.\"",
        "\"How is Precision Calibration Services performing on turnaround time?\"",
        "\"Are we over-calibrating any tool types?\"",
        "\"What are projected calibration costs for the next quarter?\"",
        "\"Which tools have failed calibration in the past 12 months?\"",
        "\"List all gaussmeters by location.\"",
    ]
    for q in query_examples:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {q}", S['BulletItem']))

    elements.append(Paragraph(
        'The agent uses read-only SQL access. It cannot modify, delete, or create records through the '
        'Q&A interface. All data-modifying operations require explicit API calls through the authenticated UI.',
        S['Callout']
    ))

    elements.append(Paragraph("Responding to Notifications", S['SectionTitle']))
    elements.append(Paragraph(
        "The agent generates proactive notifications based on configured thresholds. When instruments "
        "enter the EXPIRING SOON, CRITICAL, or OVERDUE status bands, stakeholders receive email alerts "
        "with specific instrument details and recommended actions. Escalation follows a multi-level "
        "chain: calibration manager \u2192 quality manager \u2192 plant manager, with time-based triggers.",
        S['BodyText11']
    ))

    elements.append(PageBreak())
    return elements


def build_chapter_6(S):
    """Chapter 6: Audit Preparedness"""
    elements = []
    elements.append(chapter_header_bar("AUDIT PREPAREDNESS", 6))
    elements.append(Paragraph("Audit Preparedness", S['ChapterTitle']))

    elements.append(Paragraph("One-Click Audit Package Generation", S['SectionTitle']))
    elements.append(Paragraph(
        "The Evidence page provides one-click generation of audit-ready evidence packages. Select the "
        "scope (all current, overdue only, or expiring soon) and format (PDF or JSON), then click "
        "Download. The system generates a comprehensive package in seconds.",
        S['BodyText11']
    ))

    elements.append(Paragraph("PDF Evidence Package Contents", S['SubSection']))
    pdf_contents = [
        "<b>Cover Page:</b> Organization branding, total equipment count, compliance rate, generation timestamp.",
        "<b>Executive Summary:</b> AI-generated overview of calibration program health, key metrics, and "
        "flagged items requiring attention.",
        "<b>Equipment Detail Table:</b> Every tracked instrument with asset tag, type, manufacturer, last "
        "calibration date, next due date, status indicator, and most recent result.",
        "<b>Non-Conformance Section:</b> Any out-of-tolerance, failed, or conditional results listed "
        "separately with investigation status.",
        "<b>Branded Footer:</b> Organization logo, address, and confidentiality notice on every page.",
    ]
    for item in pdf_contents:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {item}", S['BulletItem']))

    elements.append(Paragraph("ISO 17025 Compliance Reporting", S['SectionTitle']))
    elements.append(Paragraph(
        "The agent tracks compliance against ISO/IEC 17025 requirements for calibration and testing "
        "laboratories. Key reporting capabilities include:",
        S['BodyText11']
    ))
    iso_items = [
        "Traceability chain verification: every calibration links to an accredited laboratory with "
        "NIST-traceable standards.",
        "Certificate completeness validation: required fields verified on every uploaded certificate.",
        "Measurement uncertainty documentation: tracked per instrument type and vendor.",
        "Interval justification: statistical basis for calibration frequencies based on historical data.",
        "Personnel competency linkage: calibrations attributed to named technicians.",
        "Environmental condition tracking: where recorded on certificates.",
    ]
    for item in iso_items:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {item}", S['BulletItem']))

    elements.append(Paragraph("Auditor Walkthrough Mode", S['SectionTitle']))
    elements.append(Paragraph(
        "When an auditor visits, use the Evidence page to demonstrate compliance in under 30 seconds:",
        S['BodyText11']
    ))
    walkthrough = [
        "Open the Dashboard \u2014 show real-time compliance rate and status distribution.",
        "Navigate to Evidence \u2014 generate a full audit package (PDF) with one click.",
        "Open the downloaded PDF \u2014 show the cover page with compliance summary.",
        "Use Ask Agent \u2014 query any specific instrument the auditor asks about.",
        "Show the audit log \u2014 every action is timestamped and attributed.",
    ]
    for i, step in enumerate(walkthrough, 1):
        elements.append(Paragraph(f"<bullet>{i}.</bullet> {step}", S['BulletItem']))

    elements.append(Paragraph("Immutable Audit Logging", S['SectionTitle']))
    elements.append(Paragraph(
        "Every action in the system is recorded in an immutable audit log with the following attributes: "
        "timestamp, user ID, action type, entity type (tool, calibration, user), entity ID, old values, "
        "new values, and IP address. Audit log entries cannot be modified or deleted, ensuring full "
        "traceability for regulatory compliance. This satisfies 21 CFR Part 11 requirements for electronic "
        "records in FDA-regulated environments.",
        S['BodyText11']
    ))

    elements.append(Paragraph(
        '<b>30-Second Audit Demo:</b> Dashboard \u2192 Evidence Download \u2192 PDF Review \u2192 Live Q&A. '
        'No preparation needed. The system is always audit-ready.',
        S['Callout']
    ))

    elements.append(PageBreak())
    return elements


def build_chapter_7(S):
    """Chapter 7: Advanced Features"""
    elements = []
    elements.append(chapter_header_bar("ADVANCED FEATURES", 7))
    elements.append(Paragraph("Advanced Features", S['ChapterTitle']))

    elements.append(Paragraph("Calibration Drift Trend Analysis", S['SectionTitle']))
    elements.append(Paragraph(
        "The agent analyzes calibration history across all instruments to detect drift patterns. By comparing "
        "planned calibration intervals against actual measurement results over time, the system identifies "
        "instruments trending toward out-of-tolerance conditions before they fail. Ask: \"Which tools show "
        "drift trends?\" or \"Are any instruments trending toward failure?\"",
        S['BodyText11']
    ))

    elements.append(Paragraph("Predictive Equipment Recommendations", S['SectionTitle']))
    elements.append(Paragraph(
        "Based on failure rate analysis by tool type, vendor performance data, and environmental factors, "
        "the agent provides recommendations for preventive action. If a category of instruments shows a "
        "failure rate exceeding 10%, the system flags the category and recommends interval reduction, vendor "
        "change, or equipment replacement.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Interval Adjustment Optimization", S['SectionTitle']))
    elements.append(Paragraph(
        "One of the most impactful cost-saving features. The agent compares actual calibration frequencies "
        "against planned intervals to identify over-calibration (calibrating more often than necessary) and "
        "under-calibration (extending intervals beyond manufacturer recommendations). Ask: \"Are we "
        "over-calibrating any tool types?\" to see a variance report showing potential savings.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Vendor Consolidation Analysis", S['SectionTitle']))
    elements.append(Paragraph(
        "The agent evaluates vendor performance across multiple dimensions: average turnaround time, "
        "quality scores, on-time delivery percentage, cost per calibration, and accreditation scope. "
        "This analysis supports strategic vendor consolidation decisions. Ask: \"How are our vendors "
        "performing?\" or \"Compare vendor turnaround times.\"",
        S['BodyText11']
    ))

    elements.append(Paragraph("Multi-Location Equipment Tracking", S['SectionTitle']))
    elements.append(Paragraph(
        "For organizations with multiple facilities, the agent tracks instruments by location and building. "
        "Equipment can be filtered, grouped, and reported by physical location. Transfer between locations "
        "is logged in the audit trail. Ask: \"Show me all tools at [building name]\" or \"Which locations "
        "have overdue instruments?\"",
        S['BodyText11']
    ))

    elements.append(Paragraph("Recall Management", S['SectionTitle']))
    elements.append(Paragraph(
        "When an out-of-tolerance condition is detected on a calibration standard or reference instrument, "
        "the system supports retroactive invalidation of all calibrations performed using that standard. "
        "The recall capability identifies every affected instrument, flags their calibration records, and "
        "generates a full audit trail of the recall event. This is critical for automotive (IATF 16949) and "
        "aerospace (AS9100) compliance.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Escalation Rules Configuration", S['SectionTitle']))
    elements.append(Paragraph(
        "Escalation rules define the notification hierarchy for calibration events. Rules are time-based "
        "and multi-level, configured in the tenant kernel:",
        S['BodyText11']
    ))

    esc_table = make_table(
        ["Trigger", "Threshold", "Notification Target", "Action"],
        [
            ["Expiring Soon", "30 days before due", "Calibration Technician", "Schedule calibration"],
            ["Critical", "7 days before due", "Calibration Manager", "Expedite scheduling"],
            ["Overdue", "Past due date", "Quality Manager", "Remove from service"],
            ["Overdue + 7 days", "7 days past due", "Plant Manager", "Executive escalation"],
            ["Out of Tolerance", "On detection", "Quality Manager + Cal Manager", "Investigation required"],
        ],
        col_widths=[95, 95, 130, 160]
    )
    elements.append(esc_table)

    elements.append(Paragraph("Seasonal Analysis & Batch Scheduling", S['SectionTitle']))
    elements.append(Paragraph(
        "The agent analyzes monthly calibration volumes to identify seasonal patterns. Months with volumes "
        "exceeding 1.5x the average are flagged as heavy months. This enables proactive batch scheduling "
        "with vendors, reducing rush fees and turnaround times. Ask: \"Which months are heaviest for "
        "calibrations?\" or \"Can we batch our next quarter's work?\"",
        S['BodyText11']
    ))

    elements.append(PageBreak())
    return elements


def build_chapter_8(S):
    """Chapter 8: Administration"""
    elements = []
    elements.append(chapter_header_bar("ADMINISTRATION", 8))
    elements.append(Paragraph("Administration", S['ChapterTitle']))

    elements.append(Paragraph("User Role Management", S['SectionTitle']))
    elements.append(Paragraph(
        "The platform supports two role levels, enforced through JWT claims on every API request:",
        S['BodyText11']
    ))
    role_table = make_table(
        ["Capability", "Admin", "Standard User"],
        [
            ["View dashboard and equipment", "\u2713", "\u2713"],
            ["Ask agent questions", "\u2713", "\u2713"],
            ["Download evidence packages", "\u2713", "\u2713"],
            ["Upload calibration certificates", "\u2713", "\u2713"],
            ["Add/edit equipment records", "\u2713", "\u2717"],
            ["Bulk CSV import", "\u2713", "\u2717"],
            ["Delete equipment", "\u2713", "\u2717"],
            ["Upload company logo", "\u2713", "\u2717"],
            ["Manage user accounts", "\u2713", "\u2717"],
        ],
        col_widths=[250, 80, 80]
    )
    elements.append(role_table)

    elements.append(Paragraph("Notification Channel Configuration", S['SectionTitle']))
    elements.append(Paragraph(
        "Notification channels are configured in the tenant kernel. The agent currently supports email "
        "notifications via Mailgun with domain-level allowlisting. Notifications can be configured for:",
        S['BodyText11']
    ))
    notif_items = [
        "Calibration due alerts (configurable thresholds: 30-day, 7-day)",
        "Overdue instrument escalation",
        "Out-of-tolerance detection alerts",
        "Weekly compliance summary reports",
        "Monthly audit preparation reminders",
    ]
    for item in notif_items:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {item}", S['BulletItem']))

    elements.append(Paragraph("Tenant Kernel Configuration", S['SectionTitle']))
    elements.append(Paragraph(
        "The tenant kernel (TTC configuration file) controls all agent behavior for your organization. "
        "Modifications to the kernel require platform operator access. Configurable parameters include:",
        S['BodyText11']
    ))
    config_items = [
        "Company profile: name, industry, locations, compliance standards",
        "Approved vendors: names, accreditation details, NIST traceability, scope",
        "Alert thresholds: warn days, critical days, overdue escalation timing",
        "Email routing: recipients per alert level and escalation chain",
        "Equipment categories: types tracked, criticality classifications",
        "Branding: logo, color scheme, address, phone, website (for PDF output)",
        "Query templates: parameterized SQL patterns for custom reporting",
    ]
    for item in config_items:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {item}", S['BulletItem']))

    elements.append(Paragraph("Data Backup and Recovery", S['SectionTitle']))
    elements.append(Paragraph(
        "All calibration data is stored in Supabase (managed PostgreSQL) with automated daily backups, "
        "point-in-time recovery (up to 7 days on Pro plan), and geographic redundancy. Certificate files "
        "are stored in Supabase Storage with redundant storage. The platform operator maintains local "
        "backup copies of all tenant data as an additional recovery option.",
        S['BodyText11']
    ))

    elements.append(Paragraph("API Access for Integration", S['SectionTitle']))
    elements.append(Paragraph(
        "The agent exposes a REST API for integration with existing ERP, QMS, and LIMS systems. All API "
        "endpoints require JWT authentication and return JSON responses. The OpenAPI specification is "
        "available at /docs (Swagger UI) and /openapi.json. Common integration patterns include:",
        S['BodyText11']
    ))
    api_items = [
        "ERP synchronization: push equipment master data from SAP, Epicor, or NetSuite",
        "QMS integration: pull compliance metrics into existing quality dashboards",
        "LIMS connectivity: receive calibration results directly from laboratory systems",
        "Email gateway: forward calibration certificates for automated processing",
    ]
    for item in api_items:
        elements.append(Paragraph(f"<bullet>&bull;</bullet> {item}", S['BulletItem']))

    elements.append(PageBreak())
    return elements


def build_chapter_9(S):
    """Chapter 9: Cost Savings Analysis"""
    elements = []
    elements.append(chapter_header_bar("COST SAVINGS ANALYSIS", 9))
    elements.append(Paragraph("Cost Savings Analysis", S['ChapterTitle']))

    elements.append(Paragraph("Detailed ROI Model", S['SectionTitle']))
    elements.append(Paragraph(
        "The following model quantifies labor hours eliminated across each calibration management function "
        "for a typical manufacturing facility with 150-250 tracked instruments:",
        S['BodyText11']
    ))

    labor_table = make_table(
        ["Function", "Manual Hrs/Week", "Agent-Managed Hrs/Week", "Weekly Savings", "Annual Savings (50 wks)"],
        [
            ["Certificate processing", "6-8 hrs", "0.5 hrs", "6.5 hrs", "325 hrs"],
            ["Schedule tracking", "3-4 hrs", "0 hrs", "3.5 hrs", "175 hrs"],
            ["Status reporting", "2-3 hrs", "0 hrs", "2.5 hrs", "125 hrs"],
            ["Vendor communication", "2-3 hrs", "0.5 hrs", "2.0 hrs", "100 hrs"],
            ["Audit preparation", "2-4 hrs", "0.25 hrs", "2.75 hrs", "137 hrs"],
            ["Investigation management", "1-2 hrs", "0.25 hrs", "1.25 hrs", "62 hrs"],
            ["Data entry/updates", "2-3 hrs", "0 hrs", "2.5 hrs", "125 hrs"],
            ["Total", "18-27 hrs", "1.5 hrs", "21 hrs", "1,049 hrs"],
        ],
        col_widths=[120, 85, 95, 85, 95]
    )
    elements.append(labor_table)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "At a fully-loaded labor rate of $40/hr, annual labor savings are approximately <b>$41,960</b>. "
        "For organizations with dedicated calibration coordinators ($55K-$75K fully loaded), the position "
        "is effectively eliminated.",
        S['BodyText11']
    ))

    elements.append(Paragraph("Risk Cost Avoidance", S['SectionTitle']))
    elements.append(Paragraph(
        "Beyond direct labor savings, the agent eliminates risk-related costs that are difficult to quantify "
        "but catastrophic when they occur:",
        S['BodyText11']
    ))
    risk_table = make_table(
        ["Risk Event", "Frequency (Manual)", "Typical Cost", "Agent Prevention"],
        [
            ["Audit nonconformance (minor)", "1-3 per audit", "$2,000 - $5,000 each", "Near-zero with continuous monitoring"],
            ["Audit nonconformance (major)", "0.5 per audit", "$10,000 - $50,000", "Eliminated \u2014 always audit-ready"],
            ["Customer escape (shipped with expired cal)", "1-2 per year", "$5,000 - $100,000", "Eliminated \u2014 overdue alerts prevent use"],
            ["Recall event (OOT reference standard)", "Rare but severe", "$50,000 - $500,000", "Immediate detection + full traceability"],
            ["FDA 483 observation", "Varies", "$100,000+", "21 CFR Part 11 compliant logging"],
        ],
        col_widths=[130, 85, 100, 165]
    )
    elements.append(risk_table)

    elements.append(Paragraph("Comparison Matrix", S['SectionTitle']))
    compare_table = make_table(
        ["Capability", "Manual/Spreadsheet", "SaaS Software", "This Agent"],
        [
            ["Certificate OCR extraction", "\u2717", "\u2717 / Partial", "\u2713 AI-powered"],
            ["Natural language Q&A", "\u2717", "\u2717", "\u2713"],
            ["Proactive alerts", "\u2717", "\u2713 (basic)", "\u2713 (intelligent)"],
            ["One-click audit packages", "\u2717", "\u2713 (limited)", "\u2713 (branded PDF)"],
            ["Drift trend analysis", "\u2717", "\u2717", "\u2713"],
            ["Interval optimization", "\u2717", "\u2717", "\u2713"],
            ["Vendor performance analytics", "\u2717", "Partial", "\u2713"],
            ["Recall traceability", "\u2717", "Partial", "\u2713 (automatic)"],
            ["Multi-tenant isolation", "N/A", "\u2713", "\u2713 (RLS + kernel)"],
            ["Prompt injection resistance", "N/A", "N/A", "\u2713 (TTC\u2122)"],
            ["Typical annual cost", "$90K - $125K", "$15K - $40K", "$8.4K - $18K"],
        ],
        col_widths=[140, 100, 100, 140]
    )
    elements.append(compare_table)

    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Payback Period", S['SubSection']))
    elements.append(Paragraph(
        "For most manufacturing facilities, the agent achieves full payback within 30-60 days when replacing "
        "manual processes, or 3-6 months when replacing existing SaaS calibration software. The breakeven "
        "calculation: (Agent monthly cost) / (Monthly labor savings + monthly risk avoidance) = payback months. "
        "Example: $1,750/mo agent / ($3,500 labor + $2,000 risk avoidance) = 0.32 months (< 2 weeks).",
        S['BodyText11']
    ))

    elements.append(Paragraph(
        '<b>Note:</b> The labor savings and cost figures above are modeled estimates based on industry-standard '
        'calibration management workflows. Actual results will vary based on equipment count, calibration '
        'complexity, existing processes, and organizational structure. Contact your platform administrator '
        'for a customized ROI assessment.',
        S['Callout']
    ))

    elements.append(PageBreak())
    return elements


def build_chapter_10(S):
    """Chapter 10: Technical Reference"""
    elements = []
    elements.append(chapter_header_bar("TECHNICAL REFERENCE", 10))
    elements.append(Paragraph("Technical Reference", S['ChapterTitle']))

    elements.append(Paragraph("API Endpoint Reference", S['SectionTitle']))
    api_table = make_table(
        ["Method", "Endpoint", "Auth", "Description"],
        [
            ["POST", "/auth/login", "None", "Authenticate user, returns JWT (7-day TTL)"],
            ["POST", "/auth/register", "None", "Create account with company code"],
            ["POST", "/auth/portal-exchange", "None", "Exchange Supabase JWT for Cal JWT"],
            ["GET", "/cal/equipment", "JWT", "List all company equipment"],
            ["POST", "/cal/equipment", "JWT (admin)", "Add new equipment record"],
            ["POST", "/cal/upload", "JWT", "Upload certificate for AI extraction"],
            ["POST", "/cal/question", "JWT", "Natural language Q&A against cal data"],
            ["POST", "/cal/download", "JWT", "Generate evidence package (PDF/JSON)"],
            ["GET", "/cal/dashboard", "JWT", "Dashboard stats and alerts"],
            ["POST", "/cal/import/template", "JWT", "Download CSV import template"],
            ["POST", "/cal/import", "JWT (admin)", "Bulk CSV equipment import"],
            ["POST", "/cal/upload-logo", "JWT (admin)", "Upload company logo for branding"],
            ["GET", "/health", "None", "Service health check"],
            ["GET", "/docs", "None", "Swagger UI (OpenAPI)"],
        ],
        col_widths=[45, 130, 70, 235]
    )
    elements.append(api_table)

    elements.append(Paragraph("Database Schema Overview", S['SectionTitle']))
    elements.append(Paragraph(
        "All tables reside in the <font face='Courier'>cal</font> schema within the Supabase PostgreSQL "
        "database. Row-Level Security is enabled on all tables with service_role bypass for backend access.",
        S['BodyText11']
    ))

    schema_table = make_table(
        ["Table", "Purpose", "Key Fields"],
        [
            ["cal.companies", "Tenant organizations", "id, name, slug, subscription_plan, max_tools"],
            ["cal.users", "Authenticated users", "id, email, password_hash, role, company_id"],
            ["cal.tools", "Equipment registry", "id, asset_tag, tool_name, tool_type, serial_number, location, cal_interval_days, calibration_status"],
            ["cal.calibrations", "Calibration records", "id, cert_number, tool_id, calibration_date, result, next_calibration_date, performed_by, cost"],
            ["cal.vendors", "Approved cal vendors", "id, vendor_name, accreditation, nist_traceable, scope_of_accreditation"],
            ["cal.attachments", "Certificate files", "id, tool_id, calibration_id, filename, mime_type"],
            ["cal.settings", "Per-tenant config", "id, company_id, key, value"],
            ["cal.email_log", "Email audit trail", "id, company_id, direction, from_address, subject, status"],
            ["cal.conversation_memory", "Agent Q&A history", "id, company_id, question, answer, feedback, used_count"],
        ],
        col_widths=[110, 110, 260]
    )
    elements.append(schema_table)

    elements.append(Paragraph("System Requirements", S['SectionTitle']))
    req_table = make_table(
        ["Component", "Requirement"],
        [
            ["Web Browser", "Chrome, Firefox, Safari, Edge (latest 2 major versions)"],
            ["Internet Connection", "Broadband (minimum 1 Mbps)"],
            ["Server (self-hosted)", "2 vCPU, 4GB RAM, 20GB storage minimum"],
            ["Docker", "Docker Engine 24+ with Compose v2"],
            ["Python", "3.11+ (backend runtime)"],
            ["Node.js", "18+ (frontend build only)"],
            ["Database", "PostgreSQL 15+ (or Supabase managed)"],
            ["AI Provider", "Anthropic API key (Claude Sonnet tier or above)"],
        ],
        col_widths=[120, 360]
    )
    elements.append(req_table)

    elements.append(Paragraph("Troubleshooting Guide", S['SectionTitle']))
    trouble_table = make_table(
        ["Symptom", "Likely Cause", "Resolution"],
        [
            ["Login returns 401", "Expired JWT or incorrect credentials", "Clear browser cache, re-enter credentials"],
            ["Certificate upload fails", "File size > 10MB or unsupported format", "Use PDF, PNG, or JPG under 10MB"],
            ["Agent returns no data", "No equipment registered yet", "Import equipment via CSV or add manually"],
            ["PDF download is blank", "No calibration records match filter", "Upload certificates before generating evidence"],
            ["Dashboard shows 0 compliance", "All tools missing calibration records", "Upload certificates for tracked instruments"],
            ["Email notifications not received", "Mailgun domain not configured", "Contact administrator to configure email"],
            ["Slow query response", "Large dataset without index", "Contact support for database optimization"],
        ],
        col_widths=[130, 150, 200]
    )
    elements.append(trouble_table)

    elements.append(Paragraph("Support", S['SectionTitle']))
    elements.append(Paragraph(
        "For technical support, contact your platform administrator. For platform-level issues, the operator "
        "can be reached through the support channels specified in your service agreement. Include your "
        "company code, a description of the issue, and any error messages displayed.",
        S['BodyText11']
    ))

    elements.append(PageBreak())
    return elements


def build_appendix_a(S):
    """Appendix A: TTC Quick Reference Card"""
    elements = []
    elements.append(chapter_header_bar("TTC QUICK REFERENCE", "A"))
    elements.append(Paragraph("Appendix A: TTC Quick Reference Card", S['ChapterTitle']))

    elements.append(Paragraph("Symbolic Operators", S['SectionTitle']))
    op_table = make_table(
        ["Symbol", "Name", "Usage"],
        [
            ["\u2192", "Route / Implies", "intent \u2192 K3a.query (route to query handler)"],
            ["\u2227", "AND", "ISO9001 \u2227 ISO17025 (both standards apply)"],
            ["\u2228", "OR", "search_name \u2228 search_serial (either match)"],
            ["\u2205", "NULL / Empty", "\u2205advisory_only \u2192 executor (not advisory, is executor)"],
            ["\u220b", "Contains", "intent \u220b {lookup, status} (intent contains these)"],
            ["\u2208", "Member of", "vendor \u2208 approved_vendors[] (vendor in approved list)"],
            ["\u2191", "Escalate / Increase", "overdue \u2192 escalate\u2191 (increase severity)"],
            ["\u2193", "De-escalate / Decrease", "resolved \u2192 priority\u2193 (lower priority)"],
            [":=", "Definition", "status := OVERDUE (defined as overdue)"],
            ["|", "Delimiter", "warn_d|critical_d|overdue_d (separated values)"],
            ["@", "Scheduled at", "DAILY@06:00 (runs daily at 6 AM)"],
            ["{}", "Object / Set", "alert_thresholds{warn_d, critical_d}"],
            ["[]", "Array / List", "approved_vendors[Precision_Cal, Transcat]"],
        ],
        col_widths=[50, 110, 320]
    )
    elements.append(op_table)

    elements.append(Paragraph("Mandarin Concept Identifiers", S['SectionTitle']))
    cn_table = make_table(
        ["Character", "Pinyin", "English Meaning", "TTC Context"],
        [
            ["\u8eab\u4efd", "sh\u0113nf\u00e8n", "Identity", "K0: Agent persona and tenant configuration"],
            ["\u51b3\u7b56", "ju\u00e9c\u00e8", "Decision", "K1: Routing and decision tree logic"],
            ["\u901a\u4fe1", "t\u014dngx\u00ecn", "Communication", "K2: Output formatting and tone"],
            ["\u6821\u51c6", "ji\u00e0ozh\u01d4n", "Calibration", "K3a: Calibration record operations"],
            ["\u5de5\u5177", "g\u014dngj\u00f9", "Tool", "K3b: Tool and vendor management"],
            ["\u5408\u89c4", "h\u00e9gu\u012b", "Compliance", "K3c: Compliance reporting"],
            ["\u7f16\u6392", "bi\u0101np\u00e1i", "Orchestration", "K4: Batch jobs and event handling"],
            ["\u5b66\u4e60", "xu\u00e9x\u00ed", "Learning", "K5: Metrics and adaptation"],
            ["\u6307\u4ee4", "zh\u01d0l\u00ecng", "Directive", "Core behavior instructions"],
            ["\u8986\u76d6", "f\u00f9g\u00e0i", "Override", "Tenant-specific configuration overrides"],
            ["\u8f93\u51fa", "\u0161\u016bch\u016b", "Output", "Response formatting rules"],
            ["\u79df\u6237", "z\u016bh\u00f9", "Tenant", "Multi-tenant scoping"],
            ["\u6279\u5904\u7406", "p\u012b ch\u01d4l\u01d0", "Batch Processing", "Scheduled automation"],
            ["\u4e8b\u4ef6", "sh\u00ecji\u00e0n", "Event", "Triggered actions"],
            ["\u6307\u6807", "zh\u01d0bi\u0101o", "Metrics", "Performance measurement"],
            ["\u9002\u5e94", "sh\u00ecy\u00ecng", "Adaptation", "Self-tuning rules"],
        ],
        col_widths=[60, 80, 100, 240]
    )
    elements.append(cn_table)

    elements.append(Paragraph("K-Block Quick Reference", S['SectionTitle']))
    kblock_ref = make_table(
        ["Block", "Load Trigger", "Typical Token Cost", "When Used"],
        [
            ["K0 (\u8eab\u4efd)", "Always", "~150 tokens", "Every single request"],
            ["K1 (\u51b3\u7b56)", "Always/Routing", "~100 tokens", "Every single request"],
            ["K2 (\u901a\u4fe1)", "On generation", "~80 tokens", "When formatting output"],
            ["K3a (\u6821\u51c6)", "On cal ops", "~200 tokens", "Calibration queries/creates"],
            ["K3b (\u5de5\u5177)", "On tool ops", "~180 tokens", "Tool/vendor management"],
            ["K3c (\u5408\u89c4)", "On reporting", "~150 tokens", "Compliance/audit reports"],
            ["K4 (\u7f16\u6392)", "Runtime only", "~200 tokens", "Batch jobs, scheduled events"],
            ["K5 (\u5b66\u4e60)", "Post-execution", "~150 tokens", "Metrics and adaptation"],
        ],
        col_widths=[80, 90, 90, 220]
    )
    elements.append(kblock_ref)

    elements.append(PageBreak())
    return elements


def build_appendix_b(S):
    """Appendix B: Sample Tenant Kernel Template"""
    elements = []
    elements.append(chapter_header_bar("TENANT KERNEL TEMPLATE", "B"))
    elements.append(Paragraph("Appendix B: Sample Tenant Kernel Template", S['ChapterTitle']))

    elements.append(Paragraph(
        "The following is an annotated template for a tenant-specific TTC kernel configuration. "
        "Replace all placeholder values (in curly braces) with your organization's details.",
        S['BodyText11']
    ))

    template_lines = [
        "# TENANT.{SLUG}.CALIBRATIONS | \u6821\u51c6",
        "> TTC v1.0 | n0v8v LLC | ORC.GP3.APP",
        "",
        '<T0 id="\u914d\u7f6e" load="always">',
        "tenant={slug}.calibrations|org={slug}|persona=CalMgr",
        "role_skill:calibration|capability_skills:[erp,xlsx,pdf,comms]",
        "db:schema_cal|auth:{AuthGroupName}",
        "voice:{technical,precise,safety_first}",
        "</T0>",
        "",
        "# \u2014 T0 defines the agent's identity and core config.",
        "# \u2014 Replace {slug} with your company slug (e.g., acme-mfg).",
        "# \u2014 voice controls response tone: technical, friendly, formal.",
        "",
        '<T1 id="\u8def\u7531" load="always">',
        "equipment|gauge\u2192cal_equipment",
        "due|schedule\u2192cal_schedule",
        "certificate\u2192cal_certificates",
        "vendor|lab\u2192cal_vendors",
        "history\u2192cal_history",
        "oor|fail\u2192cal_oor",
        "recall\u2192cal_recall",
        "cost\u2192cal_costs",
        "</T1>",
        "",
        "# \u2014 T1 maps user intent keywords to data domains.",
        "",
        '<T3 id="\u8986\u76d6" load="on_calibration">',
        "## Company-specific calibration config",
        "",
        "criticality_intervals:{",
        "  high:60,        # 60-day cal cycle for critical tools",
        "  medium:120,     # 120-day cycle for standard tools",
        "  low:365         # Annual for non-critical",
        "}",
        "",
        "preferred_vendors:{",
        "  dimensional:{Vendor_Name_1},",
        "  electrical:{Vendor_Name_2},",
        "  pressure:{Vendor_Name_3}",
        "}",
        "",
        "oor_escalation:{",
        "  cal_mgr:{Cal_Manager_Name},",
        "  quality_mgr:{Quality_Manager_Name},",
        "  plant_mgr:{Plant_Manager_Name}",
        "}",
        "",
        "locations:[{Location_1},{Location_2},{Location_3}]",
        "</T3>",
        "",
        '<T4 id="\u8f93\u51fa" load="on_response">',
        'cite:"> Source: `{table}` | CAL | {refreshed_at}"',
        "chain:schedule\u2192erp\u2192xlsx|oor\u2192calibration+erp\u2192pdf",
        "</T4>",
    ]
    template_text = "\n".join(template_lines)
    elements.append(Paragraph(template_text.replace("\n", "<br/>").replace(" ", "&nbsp;"),
                              S['CodeBlock']))

    elements.append(PageBreak())
    return elements


def build_appendix_c(S):
    """Appendix C: ISO 17025 Compliance Checklist"""
    elements = []
    elements.append(chapter_header_bar("ISO 17025 CHECKLIST", "C"))
    elements.append(Paragraph("Appendix C: ISO 17025 Compliance Checklist", S['ChapterTitle']))

    elements.append(Paragraph(
        "Use this checklist to verify your calibration program meets ISO/IEC 17025 requirements. "
        "Items marked with (\u2713) are automatically managed by the agent:",
        S['BodyText11']
    ))

    checklist = make_table(
        ["Clause", "Requirement", "Agent-Managed", "Notes"],
        [
            ["6.4.1", "Equipment records maintained", "\u2713", "Full equipment registry with history"],
            ["6.4.2", "Equipment identified uniquely", "\u2713", "Asset tags + serial numbers"],
            ["6.4.3", "Equipment calibrated before use", "\u2713", "Status tracking prevents use when overdue"],
            ["6.4.4", "Reference standards traceable to SI", "\u2713", "NIST traceability in vendor records"],
            ["6.4.5", "Intermediate checks documented", "Partial", "Agent tracks; user performs checks"],
            ["6.4.6", "Calibration status available", "\u2713", "Real-time dashboard + status labels"],
            ["6.4.7", "Out-of-service equipment identified", "\u2713", "Automatic quarantine on overdue/OOT"],
            ["6.4.8", "Correction factors applied", "Partial", "Tracked in certificate notes"],
            ["6.4.9", "Equipment protected from damage", "Manual", "Physical security is user responsibility"],
            ["6.4.10", "Equipment status labels current", "\u2713", "Labels generated from current data"],
            ["7.6.1", "Calibration intervals established", "\u2713", "Configurable per tool type"],
            ["7.6.2", "Metrological traceability documented", "\u2713", "Vendor accreditation tracked"],
            ["7.7.1", "Nonconforming work controlled", "\u2713", "OOT detection + investigation workflow"],
            ["7.8.1", "Reports include required information", "\u2713", "PDF evidence packages with all fields"],
            ["8.2.1", "Internal audits planned", "Partial", "Compliance reports support audit prep"],
            ["8.4", "Corrective actions implemented", "Partial", "Agent flags; user implements"],
        ],
        col_widths=[50, 190, 80, 160]
    )
    elements.append(checklist)

    elements.append(PageBreak())
    return elements


def build_appendix_d(S):
    """Appendix D: Glossary"""
    elements = []
    elements.append(chapter_header_bar("GLOSSARY", "D"))
    elements.append(Paragraph("Appendix D: Glossary of Terms", S['ChapterTitle']))

    glossary = [
        ("A2LA", "American Association for Laboratory Accreditation. A recognized accreditation body for ISO 17025."),
        ("AS9100", "Quality management standard for the aerospace industry, building on ISO 9001."),
        ("Asset Tag", "A unique identifier assigned to each tracked instrument (e.g., CAL-0042)."),
        ("Calibration", "The process of comparing an instrument's measurements against a known reference standard."),
        ("Calibration Interval", "The time period between required calibrations, measured in days."),
        ("Certificate", "A document issued by a calibration laboratory confirming the results of a calibration."),
        ("Compliance Rate", "The percentage of instruments with current (non-overdue) calibration status."),
        ("Critical Equipment", "Instruments whose failure would have significant impact on product quality."),
        ("Drift", "The gradual change in an instrument's accuracy over time between calibrations."),
        ("Evidence Package", "A compiled PDF or JSON document containing calibration records for audit purposes."),
        ("IATF 16949", "Quality management standard for the automotive industry."),
        ("ISO 9001", "International standard for quality management systems."),
        ("ISO/IEC 17025", "International standard for calibration and testing laboratory competence."),
        ("JWT", "JSON Web Token. The authentication mechanism used for API access."),
        ("K-Block", "A numbered section in the TTC kernel architecture (K0 through K5)."),
        ("Kernel", "The TTC configuration file that defines all agent behavior for a tenant."),
        ("NIST", "National Institute of Standards and Technology. US national metrology institute."),
        ("OOT", "Out of Tolerance. An instrument whose measurements fall outside accepted specifications."),
        ("RLS", "Row-Level Security. Database-level access control preventing cross-tenant data access."),
        ("Slug", "A URL-safe unique identifier for a company (e.g., \"acme-mfg\")."),
        ("Supabase", "Managed PostgreSQL database platform used for data storage."),
        ("Tenant", "An organization using the platform; each tenant's data is fully isolated."),
        ("TTC", "Proprietary coded agent instruction protocol by n0v8v LLC. Uses three linguistic layers for deterministic, injection-resistant agent communication."),
        ("Traceability Chain", "The documented link from an instrument's calibration through reference standards to national/international standards."),
    ]

    glossary_data = []
    for term, definition in glossary:
        glossary_data.append([
            Paragraph(f"<b>{term}</b>", S['TableCell']),
            Paragraph(definition, S['TableCell']),
        ])

    g_table = Table(glossary_data, colWidths=[100, 380])
    g_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, LIGHT_GRAY),
    ]))
    elements.append(g_table)

    elements.append(PageBreak())
    return elements


def build_back_cover(S):
    """Back cover / final page."""
    elements = []
    elements.append(Spacer(1, 200))
    elements.append(Paragraph(
        "Calibration Management Agent",
        ParagraphStyle('BackTitle', fontName='Helvetica-Bold', fontSize=20,
                       leading=26, textColor=NAVY, alignment=TA_CENTER)
    ))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "User Manual v1.0",
        ParagraphStyle('BackVer', fontName='Helvetica', fontSize=14,
                       leading=18, textColor=TEAL, alignment=TA_CENTER)
    ))
    elements.append(Spacer(1, 30))

    # Teal divider
    elements.append(HRFlowable(width="40%", thickness=2, color=TEAL,
                                spaceBefore=0, spaceAfter=20, hAlign='CENTER'))

    elements.append(Paragraph(
        "GP3.APP Agent Platform | Powered by TTC\u2122",
        ParagraphStyle('BackTTC', fontName='Helvetica', fontSize=11,
                       leading=14, textColor=SLATE, alignment=TA_CENTER)
    ))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "n0v8v LLC \u2014 Autonomous Intelligence for Industry",
        ParagraphStyle('BackN0v8v', fontName='Helvetica', fontSize=10,
                       leading=13, textColor=MID_GRAY, alignment=TA_CENTER)
    ))
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(
        f"\u00a9 {datetime.now().year} n0v8v LLC. All rights reserved.",
        ParagraphStyle('BackCopy', fontName='Helvetica', fontSize=9,
                       leading=12, textColor=MID_GRAY, alignment=TA_CENTER)
    ))
    elements.append(Paragraph(
        "GP3.APP, TTC\u2122, and the Calibration Management Agent are proprietary to n0v8v LLC. "
        "This document is confidential and intended solely for the use of the licensed organization. "
        "Reproduction or distribution without written permission is prohibited.",
        ParagraphStyle('BackDisclaimer', fontName='Helvetica', fontSize=8,
                       leading=11, textColor=MID_GRAY, alignment=TA_CENTER,
                       spaceBefore=12)
    ))
    return elements


# ═══════════════════════════════════════════════════════════
# MAIN BUILD
# ═══════════════════════════════════════════════════════════

def build_manual():
    output_path = os.path.join(os.path.dirname(__file__), "Cal_Agent_User_Manual_v1.1.pdf")

    # Create document with custom page templates
    doc = ManualDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=60,
        bottomMargin=60,
        title="Calibration Management Agent — User Manual v1.0",
        author="n0v8v LLC",
        subject="Autonomous ISO-Compliant Equipment Calibration Intelligence",
    )

    # Page templates
    content_frame = Frame(
        54, 60, PAGE_W - 108, PAGE_H - 120,
        id='content', showBoundary=0
    )
    cover_frame = Frame(
        54, 60, PAGE_W - 108, PAGE_H - 120,
        id='cover', showBoundary=0
    )

    cover_template = PageTemplate(
        id='cover',
        frames=[cover_frame],
        onPage=cover_page_draw
    )
    content_template = PageTemplate(
        id='content',
        frames=[content_frame],
        onPage=header_footer
    )

    doc.addPageTemplates([cover_template, content_template])

    # Build all content
    S = build_styles()
    elements = []

    # Cover page (uses cover template)
    elements.extend(build_cover_page(S))

    # Switch to content template
    elements.append(NextPageTemplate('content'))

    # Table of Contents
    elements.extend(build_toc(S))

    # Chapters
    elements.extend(build_chapter_1(S))
    elements.extend(build_chapter_2(S))
    elements.extend(build_chapter_3(S))
    elements.extend(build_chapter_4(S))
    elements.extend(build_chapter_5(S))
    elements.extend(build_chapter_6(S))
    elements.extend(build_chapter_7(S))
    elements.extend(build_chapter_8(S))
    elements.extend(build_chapter_9(S))
    elements.extend(build_chapter_10(S))

    # Appendices
    elements.extend(build_appendix_a(S))
    elements.extend(build_appendix_b(S))
    elements.extend(build_appendix_c(S))
    elements.extend(build_appendix_d(S))

    # Back cover
    elements.extend(build_back_cover(S))

    # Build PDF
    doc.build(elements)
    print(f"Manual generated: {output_path}")
    print(f"File size: {os.path.getsize(output_path) / 1024:.1f} KB")
    return output_path


if __name__ == "__main__":
    build_manual()
