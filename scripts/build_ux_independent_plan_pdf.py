#!/usr/bin/env python3
"""Build the detailed no-dependency UX implementation plan PDF."""

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from pathlib import Path
import sys

from reportlab.platypus import (
    CondPageBreak,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ux_plan_tracker_map import OUT_OF_PLAN, PLAN_LABELS, ROWS

OUT = "/home/zelalem/Desktop/UX_UI/INDEPENDENT_IMPLEMENTATION_PLAN.pdf"

NAVY = colors.HexColor("#1B365D")
TEAL = colors.HexColor("#0E6B7A")
INK = colors.HexColor("#1A1A1A")
MUTED = colors.HexColor("#4A5568")
RULE = colors.HexColor("#D6DEE8")
PALE = colors.HexColor("#F4F7FA")
ROW_ALT = colors.HexColor("#EEF3F7")
PALE_TEAL = colors.HexColor("#E7F2F4")


def styles():
    s = getSampleStyleSheet()
    s.add(
        ParagraphStyle(
            "CoverKicker",
            fontName="Helvetica",
            fontSize=9,
            textColor=TEAL,
            spaceAfter=6,
        )
    )
    s.add(
        ParagraphStyle(
            "CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=NAVY,
            spaceAfter=8,
        )
    )
    s.add(
        ParagraphStyle(
            "CoverSub",
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=MUTED,
            spaceAfter=8,
        )
    )
    s.add(
        ParagraphStyle(
            "H",
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=17,
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    s.add(
        ParagraphStyle(
            "H2",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14.5,
            textColor=TEAL,
            spaceBefore=9,
            spaceAfter=4,
        )
    )
    s.add(
        ParagraphStyle(
            "H3",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=NAVY,
            spaceBefore=7,
            spaceAfter=3,
        )
    )
    s.add(
        ParagraphStyle(
            "Body",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=6,
        )
    )
    s.add(
        ParagraphStyle(
            "BodyLeft",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=6,
        )
    )
    s.add(
        ParagraphStyle(
            "BulletBody",
            fontName="Helvetica",
            fontSize=10,
            leading=13.5,
            textColor=INK,
        )
    )
    s.add(
        ParagraphStyle(
            "StepBody",
            fontName="Helvetica",
            fontSize=10,
            leading=13.5,
            textColor=INK,
        )
    )
    s.add(
        ParagraphStyle(
            "Cell",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=INK,
        )
    )
    s.add(
        ParagraphStyle(
            "Th",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
        )
    )
    s.add(
        ParagraphStyle(
            "Note",
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12.5,
            textColor=MUTED,
            spaceAfter=8,
        )
    )
    s.add(
        ParagraphStyle(
            "SqlBlock",
            fontName="Courier",
            fontSize=8,
            leading=11,
            textColor=INK,
        )
    )
    s.add(
        ParagraphStyle(
            "Caption",
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            textColor=MUTED,
            spaceAfter=8,
            spaceBefore=2,
        )
    )
    return s


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        16 * mm,
        A4[1] - 7.5 * mm,
        "MoH Analytics Portal  |  Independent implementation plan  |  detailed  |  no design wait",
    )
    canvas.setFillColor(RULE)
    canvas.rect(0, 0, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(16 * mm, 5 * mm, "UX_UI  |  20 September 2026  |  live metadata")
    canvas.drawRightString(A4[0] - 16 * mm, 5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def p(text, style):
    return Paragraph(text, style)


def esc(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def bullets(items, st):
    return ListFlowable(
        [
            ListItem(Paragraph(i, st["BulletBody"]), leftIndent=10, bulletColor=TEAL)
            for i in items
        ],
        bulletType="bullet",
        start="disc",
        leftIndent=16,
        bulletFontName="Helvetica",
        bulletFontSize=9,
        spaceAfter=8,
    )


def numbered(items, st):
    return ListFlowable(
        [
            ListItem(Paragraph(i, st["StepBody"]), leftIndent=12, bulletColor=NAVY)
            for i in items
        ],
        bulletType="1",
        start="1",
        leftIndent=18,
        bulletFontName="Helvetica-Bold",
        bulletFontSize=9,
        spaceAfter=8,
    )


def make_table(headers, rows, col_widths, st):
    data = [[p(h, st["Th"]) for h in headers]]
    for row in rows:
        data.append([p(c, st["Cell"]) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.3, RULE),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    t.setStyle(TableStyle(cmds))
    return t


def sql_box(text, st, width):
    html = esc(text).replace(" ", "&nbsp;").replace("\n", "<br/>")
    inner = Paragraph(html, st["SqlBlock"])
    t = Table([[inner]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), 0.4, RULE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return t


def callout(title, body, st, width):
    inner = [
        Paragraph(f"<b>{title}</b>", st["H3"]),
        Paragraph(body, st["BodyLeft"]),
    ]
    t = Table([[inner]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_TEAL),
                ("BOX", (0, 0), (-1, -1), 0.5, TEAL),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return t


def build():
    st = styles()
    doc = SimpleDocTemplate(
        OUT,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title="Independent implementation plan — MoH Analytics Portal (detailed)",
        author="Implementation notes from live Superset metadata",
    )
    story = []
    W = 178 * mm

    # ------------------------------------------------------------------ cover
    story.append(p("SYM-HABT-2026-09-001  ·  ONE REPO  ·  NO WAITING  ·  DETAILED", st["CoverKicker"]))
    story.append(p("Independent implementation plan", st["CoverTitle"]))
    story.append(
        p(
            "Work you can finish without ministry decisions, design-pack sign-off, "
            "emblem artwork, WHO thresholds, Amharic, or a second GitHub repository. "
            "Laptop and TV stay in this same project. One dataset fix updates both screens.",
            st["CoverSub"],
        )
    )
    story.append(
        p(
            "Source: live Superset metadata read on 20 September 2026 — 4 dashboards, "
            "69 datasets, 219 charts. Bindings below are from <b>slices.params</b> and "
            "<b>query_context</b>, joined to virtual-dataset SQL. Colour schemes "
            "<b>mohTvSequential</b> and <b>mohTvCategorical</b> are already registered "
            "on the running instance; zero charts select them.",
            st["Note"],
        )
    )

    story.append(p("How to use this document", st["H"]))
    story.append(
        p(
            "This is a playbook, not a slide deck. Each task has Where (the click path), "
            "What is wrong (the live binding), How (the exact change), Check (SQL or "
            "screenshot), and Done when. Do Wave 1 before Wave 2. Do Wave 3 last so the "
            "wall does not enlarge the same false numbers.",
            st["Body"],
        )
    )
    story.append(
        make_table(
            ["Section", "What you will actually do"],
            [
                ["0–2", "Confirm one repo, ticket prefixes, and the three click paths (Dataset SQL, Explore, git)."],
                ["3  Wave 1", "Edit two virtual datasets. Stop emitting -1. Keep data_status. Backup SQL first."],
                ["4  Wave 2", "Rebind 20 charts. Metric, filter, colour, row_limit, subheader. Save overwrite."],
                ["5  Wave 3", "Change moh_assets.py fit() / skip-blank / ASK AI CSS, and stop 22px on laptop theme."],
                ["6–8", "Screenshot checklist, rollback, ID index, out of scope."],
            ],
            [W * 0.22, W * 0.78],
            st,
        )
    )

    story.append(p("0. What this plan is, and is not", st["H"]))
    story.append(
        p(
            "Every task below is either a save in the Superset portal or a small change "
            "in moh-superset. Nothing waits on a designer or a ministry meeting.",
            st["Body"],
        )
    )
    story.append(
        make_table(
            ["In this PDF (do now)", "Left out on purpose (blocked)"],
            [
                [
                    "Sentinel -1 / empty-vs-zero, map colour, row limits, KPI units, PHEM CFR arithmetic, TV scale() and skip-blank, ASK AI hidden on TV, 22px off laptop theme",
                    "FDRE/MoH emblems, WHO/MoH epidemic numbers, Amharic, footer brand, in-portal feedback product, native-vs-HTML TV rewrite, custom KPI React, Shepherd left-rail, Nobert traffic-light HTML",
                ],
                [
                    "One git repo: moh-superset. TV page is already GET /moh-static/tv",
                    "A second repo for TV. That would duplicate SQL and drift.",
                ],
            ],
            [W * 0.52, W * 0.48],
            st,
        )
    )

    story.append(p("1. How laptop and TV share work", st["H"]))
    story.append(
        p(
            "You do not need two repositories. The laptop opens dashboards 3 and 8 in "
            "the portal. The TV opens the same dashboard 8 through "
            "<font face='Courier'>superset/moh_assets.py</font> at "
            "<font face='Courier'>/moh-static/tv</font> (iframe, standalone=2). "
            "If you fix malaria SQL once, both screens stop showing -1.0. If you only "
            "change the TV page, the laptop still lies.",
            st["Body"],
        )
    )
    story.append(
        make_table(
            ["Surface", "URL / entry", "What to change here"],
            [
                [
                    "Laptop",
                    "Dashboard 3 (MOH Performance Monitering) and 8 (Inteligence)",
                    "Dataset SQL + Explore (colour, metric, filter, row_limit, subheader)",
                ],
                [
                    "TV",
                    "/moh-static/tv  (iframe of dashboard 8)",
                    "After SQL is fixed: stop CSS scale(); skip slides that did not load; hide ASK AI",
                ],
            ],
            [W * 0.18, W * 0.42, W * 0.40],
            st,
        )
    )
    story.append(
        p(
            "Dashboard 1 is the old v0 copy. Do not spend time on it. Dashboard 10 is "
            "Usage. This plan only touches 3 and 8.",
            st["Note"],
        )
    )

    story.append(CondPageBreak(70 * mm))
    story.append(p("2. Two kinds of ticket only", st["H"]))
    story.append(
        make_table(
            ["Prefix", "Where you click", "Git?"],
            [
                [
                    "[NOCODE-SQL]",
                    "Superset → Settings / Data → Datasets → open dataset → Edit dataset → SQL Lab tab → Save",
                    "No",
                ],
                [
                    "[NOCODE-CHART]",
                    "Superset → Charts → open chart → Explore → change metric / filter / colour / row limit → Save (overwrite)",
                    "No",
                ],
                [
                    "[CODE]",
                    "This repo: superset/moh_assets.py and the running superset_config.py → restart Flask / gunicorn",
                    "Yes",
                ],
            ],
            [W * 0.22, W * 0.58, W * 0.20],
            st,
        )
    )
    story.append(
        p(
            "Do not put “fix malaria” on one ticket. It is SQL, then several chart saves, "
            "then (later) TV skip-blank. Mixing them hides that the first two do not need "
            "a frontend build.",
            st["Note"],
        )
    )

    story.append(p("3. Order of work", st["H"]))
    story.append(
        make_table(
            ["Wave", "When", "What", "Owner", "Hours"],
            [
                ["1", "Day 1 morning", "Dataset SQL: stop emitting -1; keep data_status", "Whoever can edit datasets", "2–3"],
                ["2", "Day 1 afternoon + Day 2", "Rebind malaria, maternal, RHI, PHEM, Summary, Equity charts", "Whoever can edit charts", "5–7"],
                ["3", "Day 3", "TV: no scale(); skip empty; hide ASK AI; 22px off laptop theme", "Engineer in this repo", "3–4"],
            ],
            [W * 0.10, W * 0.22, W * 0.38, W * 0.18, W * 0.12],
            st,
        )
    )
    story.append(
        p(
            "Wave 3 does not wait on design. It only waits on Wave 1–2 so the wall does "
            "not show the same -1.0 in larger type.",
            st["Note"],
        )
    )

    story.append(p("3a. Excel tracker map", st["H"]))
    story.append(
        p(
            "File: <b>Week2_Task_Tracker(1).xlsx</b> → sheet <b>Independent plan map</b> "
            "(also INDEPENDENT_PLAN_TRACKER_MAP.csv). Tracker Task IDs are the first "
            "column on the Tasks sheet (F-001-A, F-002-A, …). A/B split: the "
            "<b>-A</b> row is the no-code or code fix; the <b>-B</b> row is design. "
            "This PDF only works -A slices that do not wait on design or ministry.",
            st["Body"],
        )
    )
    story.append(
        p(
            "<b>CLOSES</b> = mark the Tasks-sheet row done after the plan task. "
            "<b>PARTIAL</b> = do this slice; leave the tracker row open. "
            "<b>VERIFY</b> = tracker already DONE; confirm in the UI. "
            "<b>NEW</b> = Yengwe TV work with no tracker row.",
            st["Note"],
        )
    )
    seen = {}
    for r in ROWS:
        pid, task, wave, tid, fid, _stream, _sev, _tstat, cov, _title, _does, _rest = r
        if pid not in seen:
            seen[pid] = {"task": task, "wave": wave, "ids": [], "cov": []}
        label = f"{tid} / {fid}" if tid != "—" else "not in tracker"
        if label not in seen[pid]["ids"]:
            seen[pid]["ids"].append(label)
        if cov not in seen[pid]["cov"]:
            seen[pid]["cov"].append(cov)
    compact = [
        [
            pid,
            f"Wave {info['wave']}",
            PLAN_LABELS.get(pid, info["task"]),
            ", ".join(info["ids"]),
            " · ".join(info["cov"]),
        ]
        for pid, info in seen.items()
    ]
    story.append(
        make_table(
            ["Plan", "Wave", "Plan task", "Tracker Task ID / Finding", "Coverage"],
            compact,
            [W * 0.10, W * 0.10, W * 0.28, W * 0.32, W * 0.20],
            st,
        )
    )
    story.append(
        p(
            "Full row-by-row map (what this plan does vs what stays on the tracker) "
            "is section 12. Open the Excel sheet to filter by Coverage = CLOSES.",
            st["Note"],
        )
    )

    # ------------------------------------------------------------------ click paths
    story.append(CondPageBreak(35 * mm))
    story.append(p("4. How you click — three recipes you will repeat", st["H"]))
    story.append(
        p(
            "Read this page once. Every later task only names the dataset or chart and "
            "the field to change.",
            st["Body"],
        )
    )

    story.append(p("4.1 Backup, then edit a virtual dataset  [NOCODE-SQL]", st["H2"]))
    story.append(
        numbered(
            [
                "Log in as a user who can edit datasets (Admin or the dataset owner).",
                "Top menu → <b>Settings</b> (or Data) → <b>Datasets</b>.",
                "Search by name (example: <font face='Courier'>malaria_risk_data</font>). Open the row. Confirm the numeric id in the URL matches the id in this PDF.",
                "Click <b>Edit</b> (pencil) → tab <b>Query / SQL</b>.",
                "Select all SQL → copy into a local file, for example "
                "<font face='Courier'>~/Desktop/UX_UI/backups/ds_28_before.sql</font>. That file is your rollback.",
                "Make only the replacements named in the task. Do not rewrite Jinja "
                "(<font face='Courier'>{% if filter_values(...) %}</font> blocks). Do not drop the UNION of region polygons.",
                "Click <b>Run</b> / preview. If ClickHouse errors, paste the error next to the backup and stop.",
                "Click <b>Save</b>. If prompted, <b>Sync columns from source</b>. You are not adding columns; you are changing values of existing ones.",
                "Open <b>Dataset → Preview</b> and run the Check SQL from the task.",
            ],
            st,
        )
    )

    story.append(p("4.2 Rebind a chart  [NOCODE-CHART]", st["H2"]))
    story.append(
        numbered(
            [
                "From the dashboard: hover the chart → ⋯ → <b>Edit chart</b>. Or Charts list → search the chart id.",
                "You are in Explore. Left = Data (metrics, filters, row limit). Right = Customize (colour, number format, subheader).",
                "Change only what the task lists. Click <b>Update chart</b> / Run and look at the preview.",
                "Click <b>Save</b> → overwrite the existing chart. Do not Save as a new slice (the dashboard would keep the old one).",
                "Return to the dashboard. Hard-refresh (Ctrl+Shift+R). Screenshot the chart for the checklist in section 9.",
            ],
            st,
        )
    )
    story.append(
        p(
            "How to add a simple filter: Data → Filters → + Filter → column "
            "<font face='Courier'>data_status</font> → operator Equals (or IN) → value "
            "<font face='Courier'>has_data</font>. How to add a SQL filter: Filters → "
            "+ → Custom SQL → paste the WHERE fragment from the task (no leading WHERE).",
            st["Note"],
        )
    )

    story.append(p("4.3 Colour scheme  [NOCODE-CHART]", st["H2"]))
    story.append(
        p(
            "Explore → Customize → Linear colour scheme (maps) or Colour scheme (bars). "
            "Pick <b>MoH TV — Single Hue, Dark = More</b> (id mohTvSequential) for "
            "choropleths. Pick <b>MoH TV — Four Series, No Red/Green Pair</b> "
            "(id mohTvCategorical) for PHEM regional bars. If the dropdown does not "
            "list them, they are registered in the running superset_config.py as "
            "EXTRA_SEQUENTIAL_COLOR_SCHEMES / EXTRA_CATEGORICAL_COLOR_SCHEMES — restart "
            "the app, then retry. Do not invent new hex values.",
            st["Body"],
        )
    )

    story.append(
        callout(
            "Map outlines after you stop using -1",
            "The SQL currently writes toFloat64(-1) so deck.gl still draws a polygon when "
            "“Ignore null locations” is ON. After you switch to NULL you must turn "
            "<b>Ignore null locations / filter_nulls OFF</b> on every deck_polygon that "
            "needs region borders. Colour still comes only from has_data rows; NULL "
            "rows draw an unfilled outline. If you leave filter_nulls ON, region "
            "outlines disappear.",
            st,
            W,
        )
    )

    # ------------------------------------------------------------------ WAVE 1
    story.append(CondPageBreak(40 * mm))
    story.append(p("5. Wave 1 — Dataset SQL (no git)", st["H"]))
    story.append(
        p(
            "These two datasets UNION region outline polygons with woreda polygons and "
            "set missing metrics to -1 so the map still draws a border. Charts then "
            "AVG / colour that -1. data_status already exists and is unused by almost "
            "every chart. You will stop manufacturing -1 and start filtering on data_status.",
            st["Body"],
        )
    )

    story.append(p("T1 — malaria_risk_data (dataset 28) — stop manufacturing -1", st["H2"]))
    story.append(p("<b>Where:</b> Datasets → malaria_risk_data (id 28) → Edit SQL", st["BodyLeft"]))
    story.append(
        p(
            "<b>What is wrong:</b> CTE <font face='Courier'>region_shapes</font> sets "
            "<font face='Courier'>risk_index_final = toFloat64(-1)</font>. CTE "
            "<font face='Courier'>woreda_shapes</font> uses multiIf so unmapped and "
            "no_data woredas also get -1. Chart 99 is AVG(risk_index_final), so an empty "
            "extract prints <b>-1.0</b>. Chart 103 colours those rows, so the legend "
            "becomes <b>-1 – -1</b>. Dataset columns (live): centroid_*, climate_region, "
            "data_status, geometry_geojson, layer_type, malaria_cases, morbidity_per_1000, "
            "period_text, positivity_rate, region, risk_category, risk_index_final, "
            "season, woreda, woreda_id, woreda_name, zone. There is <b>no period_date "
            "column</b> — every malaria chart still filters on it.",
            st["Body"],
        )
    )
    story.append(p("Replace these three assignments. Leave data_status as it is.", st["BodyLeft"]))
    story.append(p("A. region_shapes — risk index", st["H3"]))
    story.append(p("Find:", st["Caption"]))
    story.append(
        sql_box("toFloat64(-1) AS risk_index_final,", st, W)
    )
    story.append(p("Replace with:", st["Caption"]))
    story.append(
        sql_box("CAST(NULL AS Nullable(Float64)) AS risk_index_final,", st, W)
    )
    story.append(Spacer(1, 4))
    story.append(p("B. woreda_shapes — the multiIf on unmatched / no_data woredas", st["H3"]))
    story.append(p("Find:", st["Caption"]))
    story.append(
        sql_box(
            "multiIf(\n"
            "    s.ou_id IS NULL, toFloat64(-1),\n"
            "    rm.woreda_id IS NULL, toFloat64(-1),\n"
            "    rm.risk_index_final\n"
            ") AS risk_index_final,",
            st,
            W,
        )
    )
    story.append(p("Replace with:", st["Caption"]))
    story.append(
        sql_box(
            "multiIf(\n"
            "    s.ou_id IS NULL, CAST(NULL AS Nullable(Float64)),\n"
            "    rm.woreda_id IS NULL, CAST(NULL AS Nullable(Float64)),\n"
            "    rm.risk_index_final\n"
            ") AS risk_index_final,",
            st,
            W,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        p(
            "Do not delete the UNION ALL of region_shapes. Do not change malaria_cases "
            "or morbidity (they are already NULL on region rows). Save. Sync columns if asked.",
            st["Body"],
        )
    )
    story.append(p("Check — Dataset preview or SQL Lab wrapping this dataset:", st["H3"]))
    story.append(
        sql_box(
            "SELECT data_status, layer_type,\n"
            "       count() AS n,\n"
            "       countIf(risk_index_final IS NULL) AS null_risk,\n"
            "       countIf(risk_index_final < 0) AS neg_risk,\n"
            "       min(risk_index_final) AS min_risk,\n"
            "       max(risk_index_final) AS max_risk\n"
            "FROM malaria_risk_data   -- or paste the virtual SQL as a subquery\n"
            "GROUP BY data_status, layer_type\n"
            "ORDER BY layer_type, data_status",
            st,
            W,
        )
    )
    story.append(
        p(
            "<b>Done when:</b> neg_risk = 0 for every group. Rows with data_status in "
            "(no_data, unmapped, region) have null_risk = n. has_data rows have a real "
            "min_risk ≥ 0. Region outline rows still exist (layer_type = region).",
            st["Body"],
        )
    )

    story.append(CondPageBreak(55 * mm))
    story.append(p("T2 — woreda_region_map (dataset 53) — same sentinel rule", st["H2"]))
    story.append(p("<b>Where:</b> Datasets → woreda_region_map (id 53) → Edit SQL", st["BodyLeft"]))
    story.append(
        p(
            "<b>What is wrong:</b> The header comment tells authors to add a "
            "<b>-999 to -1 legend bucket</b> for no_data / unmapped / region rows. That "
            "comment is the defect (tracker F-002). Three places assign "
            "<font face='Courier'>toFloat64(-1)</font> to target_achievement_pct: "
            "region_shapes (two SELECTs, the second is the Jinja org_unit_selection "
            "escape hatch), and woreda_shapes multiIf when wm.region is NULL or "
            "achievement is NULL. Chart 74 then colours maternal deaths with "
            "AVG(target_achievement_pct) so missing woredas sit on the colour ramp.",
            st["Body"],
        )
    )
    story.append(p("C. Delete or rewrite the header comment that asks for a -1 legend bucket", st["H3"]))
    story.append(p("Find this block at the top of the SQL and replace the colour-breakpoint sentence:", st["Caption"]))
    story.append(
        sql_box(
            "--   Color breakpoints: add an explicit -999 to -1 bucket (grey)\n"
            "--   for no_data/unmapped/region rows, then your normal 0-20 / ...",
            st,
            W,
        )
    )
    story.append(p("Replace with:", st["Caption"]))
    story.append(
        sql_box(
            "--   Color: only has_data rows. Region / no_data / unmapped emit NULL\n"
            "--   achievement so they are not on the ramp. Keep Ignore-null-locations OFF\n"
            "--   so region outlines still draw.",
            st,
            W,
        )
    )
    story.append(p("D. region_shapes — both toFloat64(-1) assignments (plain SELECT and the Jinja UNION)", st["H3"]))
    story.append(p("Find (appears twice):", st["Caption"]))
    story.append(
        sql_box("toFloat64(-1) AS target_achievement_pct,", st, W)
    )
    story.append(p("Replace both with:", st["Caption"]))
    story.append(
        sql_box("CAST(NULL AS Nullable(Float64)) AS target_achievement_pct,", st, W)
    )
    story.append(p("E. woreda_shapes multiIf", st["H3"]))
    story.append(p("Find:", st["Caption"]))
    story.append(
        sql_box(
            "multiIf(\n"
            "    wm.region IS NULL, toFloat64(-1),\n"
            "    wm.target_achievement_pct IS NULL, toFloat64(-1),\n"
            "    wm.target_achievement_pct\n"
            ") AS target_achievement_pct,",
            st,
            W,
        )
    )
    story.append(p("Replace with:", st["Caption"]))
    story.append(
        sql_box(
            "multiIf(\n"
            "    wm.region IS NULL, CAST(NULL AS Nullable(Float64)),\n"
            "    wm.target_achievement_pct IS NULL, CAST(NULL AS Nullable(Float64)),\n"
            "    wm.target_achievement_pct\n"
            ") AS target_achievement_pct,",
            st,
            W,
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        p(
            "Keep data_status and layer_type. Keep the Jinja "
            "<font face='Courier'>{% if org_unit_selection %}</font> block — only the "
            "-1 assignment inside it changes. Save. Sync columns if asked.",
            st["Body"],
        )
    )
    story.append(
        KeepTogether(
            [
                p("Check:", st["H3"]),
                sql_box(
                    "SELECT data_status, layer_type,\n"
                    "       count() AS n,\n"
                    "       countIf(target_achievement_pct IS NULL) AS null_pct,\n"
                    "       countIf(target_achievement_pct < 0) AS neg_pct\n"
                    "FROM woreda_region_map\n"
                    "GROUP BY data_status, layer_type",
                    st,
                    W,
                ),
                p(
                    "<b>Done when:</b> neg_pct = 0. no_data / unmapped / region rows are all NULL "
                    "on target_achievement_pct. has_data rows still have 0–100+ values. "
                    "is_descending is still present (needed for death vs coverage colour later).",
                    st["Body"],
                ),
            ]
        )
    )

    # ------------------------------------------------------------------ WAVE 2 malaria
    story.append(CondPageBreak(35 * mm))
    story.append(p("6. Wave 2 — Chart rebinds (no git)", st["H"]))
    story.append(
        p(
            "Do this after T1 and T2 are saved. Open each chart in Explore. After "
            "changing, Save (overwrite). Then open the parent dashboard and hard-refresh.",
            st["Body"],
        )
    )

    story.append(p("6.1 Malaria — Intelligence dashboard 8", st["H2"]))
    story.append(
        p(
            "All of these sit on dataset 28. Live columns have <b>period_text</b>, not "
            "period_date. Every chart below still has a TEMPORAL_RANGE filter on "
            "period_date. That filter is dead. After T1, AVG(risk_index_final) will "
            "ignore NULL — but only if you also drop region/no_data rows from the KPI "
            "cards. High-risk (chart 101) is COUNT_DISTINCT(woreda_id) with "
            "risk_category IN (High, Very High). An empty set returns <b>0</b>, which "
            "looks like “no high-risk woredas” next to two No-data cards.",
            st["Body"],
        )
    )

    story.append(p("Shared filters for cards 97, 99, 100, 101, 102, 104", st["H3"]))
    story.append(
        numbered(
            [
                "Data → Filters → delete the filter whose column is period_date.",
                "If you need a time window, add Filter → period_text → IN / Equals → the season string you want (or leave unfiltered and let the dashboard native filter drive it).",
                "Add Filter → data_status → Equals → has_data.",
                "Add Filter → layer_type → Equals → woreda. (Stops region outline rows entering AVG / COUNT.)",
            ],
            st,
        )
    )

    story.append(
        make_table(
            ["Chart", "ID", "Live binding now", "Exact Explore changes"],
            [
                [
                    "Total Malaria Cases",
                    "97",
                    "big_number_total. SUM(malaria_cases). Filter: period_date TEMPORAL_RANGE “No filter”.",
                    "Shared filters. Keep SUM(malaria_cases). Empty extract must show the empty-state string, not 0 from region rows.",
                ],
                [
                    "Average risk index",
                    "99",
                    "AVG(risk_index_final) as SQL metric. Same dead period_date filter. After T1 this AVG ignores NULL — still add has_data.",
                    "Shared filters. Metric stays AVG(risk_index_final). Preview an empty climate/season: card says No data, not -1.0.",
                ],
                [
                    "Average morbidity per 1000",
                    "100",
                    "AVG(morbidity_per_1000). Same period_date filter.",
                    "Shared filters. Keep the metric.",
                ],
                [
                    "High-risk woredas",
                    "101",
                    "COUNT_DISTINCT(woreda_id). Filters: period_date + risk_category IN (High, Very High).",
                    "Keep risk_category IN (High, Very High). Add shared filters. If the preview is 0 on a season with no High rows, change the metric to the SQL below so Big Number treats empty as NULL.",
                ],
                [
                    "Top 15 highest-risk woredas",
                    "102",
                    "Bar. Metric “Risk Index”. row_limit 15. Colour googleCategory20c. period_date filter.",
                    "Shared filters. Colour mohTvSequential or mohTvCategorical. Sort descending on Risk Index.",
                ],
                [
                    "Malaria Risk Category",
                    "104",
                    "Pie. COUNT(risk_category). row_limit 100. period_date filter.",
                    "Shared filters. Colour mohTvCategorical.",
                ],
            ],
            [W * 0.20, W * 0.07, W * 0.33, W * 0.40],
            st,
        )
    )

    story.append(p("Chart 101 — metric if Big Number still prints 0 on empty", st["H3"]))
    story.append(
        p(
            "Explore → Metrics → three-dot on COUNT_DISTINCT → Edit → Custom SQL:",
            st["BodyLeft"],
        )
    )
    story.append(
        sql_box(
            "if(count() = 0, CAST(NULL AS Nullable(UInt64)),\n"
            "   countDistinct(woreda_id))",
            st,
            W,
        )
    )
    story.append(
        p(
            "Label it High-risk woredas. Save the metric on the chart (adhoc is enough; "
            "you do not have to add it to the dataset).",
            st["Note"],
        )
    )

    story.append(p("Chart 103 — Malaria Risk Distribution Heatmap", st["H3"]))
    story.append(
        p(
            "<b>Live:</b> deck_polygon, dataset 28, metric “Risk Index” "
            "(avg(risk_index_final)), row_limit <b>1000</b>, colour schemeOranges, "
            "filters period_date + geometry_geojson IS NOT NULL, extra columns include "
            "data_status and layer_type but they are not used as filters, filter_nulls implied by Ignore null locations.",
            st["Body"],
        )
    )
    story.append(
        numbered(
            [
                "Delete the period_date filter.",
                "Add SQL filter: <font face='Courier'>data_status = 'has_data' OR layer_type = 'region'</font> (keeps outlines, drops unmapped junk from the ramp).",
                "Customize → Linear colour scheme → mohTvSequential.",
                "Data → row_limit → <b>2000</b> or 5000 (Ethiopia has ~700–800 woredas plus ~12 region polygons; 1000 truncates).",
                "Map / deck controls → <b>Ignore null locations = OFF</b> (required after T1, or region outlines vanish).",
                "Legend / chart title: type “Darker = higher risk”.",
            ],
            st,
        )
    )
    story.append(
        p(
            "<b>Done when (malaria):</b> the four KPI cards agree (all Not available, or "
            "all real numbers). High-risk is not 0 beside two No-data cards. Map legend "
            "is not “-1 – -1”. Opening dashboard 8 on a laptop and /moh-static/tv shows "
            "the same numbers.",
            st["Body"],
        )
    )

    # ------------------------------------------------------------------ WAVE 2 maps
    story.append(CondPageBreak(40 * mm))
    story.append(p("6.2 Death and coverage maps", st["H2"]))
    story.append(
        p(
            "Chart 74 is the highest-severity bind. It is a maternal <b>deaths</b> map "
            "on dataset 53, but the metric is AVG(target_achievement_pct) and the colour "
            "is superset_seq_1. Query extra WHERE is "
            "<font face='Courier'>(indicator_short_name = '% of Institutional Maternal Deaths' "
            "OR layer_type = 'region')</font>. is_descending exists on the dataset for a "
            "reason: deaths are better when low. Colouring achievement % paints high "
            "deaths as “on target”.",
            st["Body"],
        )
    )

    story.append(p("Chart 74 — Institutional Maternal Deaths Heat Map", st["H3"]))
    story.append(
        make_table(
            ["Field", "Live now", "Change to"],
            [
                ["Dashboard", "8 Inteligence", "same"],
                ["Dataset", "53 woreda_region_map", "same"],
                ["Viz", "deck_polygon", "same"],
                ["Metric", "AVG(target_achievement_pct)", "AVG(total_value)  — this is the death count / rate already on the row"],
                ["SQL WHERE", "indicator_short_name = '% of Institutional Maternal Deaths' OR layer_type = 'region'", "Keep that. Add AND (data_status = 'has_data' OR layer_type = 'region')"],
                ["Linear colour", "superset_seq_1", "mohTvSequential"],
                ["Ignore null locations", "ON (filter_nulls true)", "OFF — after T2"],
                ["row_limit", "10000", "leave"],
                ["Legend / title", "none", "More deaths — worse. Darker = more deaths."],
            ],
            [W * 0.24, W * 0.40, W * 0.36],
            st,
        )
    )
    story.append(
        p(
            "After Save, run this once in SQL Lab on ClickHouse (read-only) to confirm "
            "the indicator is “better when low”. If is_descending is 0, high deaths will "
            "still paint as good even with AVG(total_value) if some other chart uses achievement %.",
            st["Body"],
        )
    )
    story.append(
        sql_box(
            "SELECT indicator_short_name, is_descending, count()\n"
            "FROM monthly_indicator_data_elements\n"
            "WHERE indicator_short_name LIKE '%Institutional Maternal Deaths%'\n"
            "GROUP BY indicator_short_name, is_descending",
            st,
            W,
        )
    )
    story.append(
        p(
            "Expect is_descending = 1. If it is 0, fix the dimension table (that is still "
            "no-code SQL / warehouse), not the chart colour.",
            st["Note"],
        )
    )

    story.append(p("Chart 89 — Institutional Early Neonatal Death Heatmap (DHIS2)", st["H3"]))
    story.append(
        p(
            "<b>Live:</b> deck_polygon, dataset 53, metric AVG(total_value) already "
            "(good), colour schemeOrRd, SQL WHERE "
            "<font face='Courier'>(indicator_short_name = '% of Neonatal Deaths' OR "
            "layer_type = 'region')</font>, extra columns do not even include data_status.",
            st["Body"],
        )
    )
    story.append(
        numbered(
            [
                "Keep AVG(total_value).",
                "Add data_status / layer_type to Extra data for JS if the control exists (Customize or Data → extra columns): layer_type, data_status.",
                "SQL WHERE: keep the indicator OR region clause; add <font face='Courier'>(data_status = 'has_data' OR layer_type = 'region')</font>.",
                "Linear colour → mohTvSequential. Ignore null locations OFF.",
                "Legend: Darker = more neonatal deaths — worse.",
            ],
            st,
        )
    )

    story.append(p("Chart 161 — Woreda Level Heatmap (dashboard 3, coverage — achievement is correct here)", st["H3"]))
    story.append(
        p(
            "<b>Live:</b> AVG(target_achievement_pct), row_limit already 2000, colour "
            "superset_seq_1, no adhoc filters, extra columns already include data_status. "
            "This map is meant to show achievement, so keep the metric. Only stop "
            "colouring -1 / no_data and switch the ramp.",
            st["Body"],
        )
    )
    story.append(
        numbered(
            [
                "SQL filter: data_status = 'has_data' OR layer_type = 'region'.",
                "Linear colour → mohTvSequential. Ignore null locations OFF.",
                "Leave row_limit 2000.",
            ],
            st,
        )
    )

    story.append(p("Charts 26, 58, 95 — leftover row_limit 1000 (same national-truncation defect as old 161)", st["H3"]))
    story.append(
        make_table(
            ["Chart", "ID", "Dashboard / dataset", "Change"],
            [
                [
                    "Map",
                    "26",
                    "Dashboard 1 (v0) / woreda_indicator_map ds 3. AVG(target_achievement_pct), row_limit 1000, superset_seq_1, period_date_greg filter.",
                    "Optional: skip v0. If you still use it, row_limit 2000 and mohTvSequential.",
                ],
                [
                    "Quarterly Map",
                    "58",
                    "Dashboard 3 / Quarterly_map_dataset ds 18. AVG(target_achievement_pct), row_limit 1000, superset_seq_1.",
                    "Data → row_limit 2000. Colour mohTvSequential. Ignore null locations OFF if the SQL uses sentinels.",
                ],
                [
                    "TB Notification Per Thousand Heatmap",
                    "95",
                    "Dashboard 8 / TB Cases notified ds 26. AVG(tb_cnr_per_1000), row_limit 1000, deck_gl_heatmap_gradient.",
                    "row_limit 2000. Colour mohTvSequential. Legend: Darker = higher TB CNR.",
                ],
            ],
            [W * 0.22, W * 0.08, W * 0.38, W * 0.32],
            st,
        )
    )

    # ------------------------------------------------------------------ KPIs PHEM equity
    story.append(CondPageBreak(40 * mm))
    story.append(p("6.3 Summary KPIs and coverage &gt; 100%  (dashboard 3, dataset 1 moh_meged_data)", st["H2"]))
    story.append(
        p(
            "Live metrics already on the dataset: Performance = AVG(value); "
            "performance capped = LEAST(AVG(value), 100); Baseline = AVG(baseline_value); "
            "Target = AVG(target_value). Column target_variance_abs already exists. "
            "You do not need a new dataset or a React KPI card.",
            st["Body"],
        )
    )
    story.append(
        make_table(
            ["Chart", "ID", "Live", "Exact Explore changes"],
            [
                [
                    "Performance",
                    "10",
                    "big_number_total, metric Performance (AVG(value)), filter period_date_greg “No filter”, no subheader.",
                    "Either switch the metric dropdown to “performance capped”, OR keep Performance and set Subheader to: Values above 100% usually mean a denominator problem, not extra coverage.",
                ],
                [
                    "Baseline",
                    "5",
                    "big_number, metric Baseline, no subheader.",
                    "Subheader: unit of the selected indicator (type “%” or “per 1,000” — whatever the dashboard filter implies). No new dataset.",
                ],
                [
                    "Target",
                    "11",
                    "big_number, AVG(target_value), no subheader.",
                    "Same subheader unit as Baseline.",
                ],
                [
                    "Variance (optional fourth card or Markdown)",
                    "—",
                    "Not on the row. Column target_variance_abs is already on moh_meged_data.",
                    "Dashboard Edit → + Empty chart / Markdown under the KPI row: “Performance minus target = target_variance_abs”. Or add a Big Number with metric AVG(target_variance_abs).",
                ],
            ],
            [W * 0.22, W * 0.08, W * 0.32, W * 0.38],
            st,
        )
    )

    story.append(p("6.4 PHEM CFR and colours  (dashboard 8, dataset 49 phem)", st["H2"]))
    story.append(
        p(
            "Dataset SQL is a straight SELECT from disease_surveillance. Columns: "
            "fiscal_year, disease, region, affected_woredas, cases, deaths, cfr, "
            "survivors, data_level, disease_region. Chart 150 SUM(cases) and 151 "
            "SUM(deaths) are correct. Chart 152 is <b>SUM(cfr)</b> with region IN "
            "(National). Summing a rate is not a rate. Do not invent WHO epidemic "
            "thresholds — that wait is out of this PDF.",
            st["Body"],
        )
    )
    story.append(
        make_table(
            ["Chart", "ID", "Live", "Exact Explore changes"],
            [
                [
                    "National CFR",
                    "152",
                    "big_number_total, SUM(cfr), region IN (National).",
                    "Keep the National filter. Metrics → + Adhoc SQL metric: SUM(deaths) * 1000 / nullIf(SUM(cases), 0). Label: National CFR. Format SMART_NUMBER. Subheader: per 1,000 suspected cases.",
                ],
                [
                    "Cases by Region",
                    "153",
                    "Bar, AVG(cases), region NOT IN (National), colour supersetColors.",
                    "Prefer SUM(cases) if each row is already one disease-region-year (AVG of one row is harmless; AVG of several diseases is wrong). Colour scheme mohTvCategorical. No threshold line.",
                ],
                [
                    "Deaths by Region",
                    "154",
                    "heatmap_v2, AVG(deaths), schemeOrRd, region NOT IN (National).",
                    "Colour mohTvSequential. Legend: Darker = more deaths.",
                ],
            ],
            [W * 0.20, W * 0.08, W * 0.32, W * 0.40],
            st,
        )
    )
    story.append(p("Adhoc SQL for chart 152 (paste as Custom SQL metric):", st["Caption"]))
    story.append(
        sql_box(
            "SUM(deaths) * 1000 / nullIf(SUM(cases), 0)",
            st,
            W,
        )
    )
    story.append(
        p(
            "Sanity check: pick one disease and one year. National CFR on the card must "
            "equal (national deaths × 1000) / national cases from charts 150 and 151, "
            "not the sum of regional CFRs.",
            st["Note"],
        )
    )

    story.append(p("6.5 Health Equity definitions  (dashboard 8, datasets 29 and 30)", st["H2"]))
    story.append(
        p(
            "The SQL already computes min, max, difference, ratio_to_minimum, "
            "distance_from_best, normalized. You are only labelling what the chart "
            "already returns. Live metrics: 112 Estimates = avg(estimate); 113 Ratio = "
            "max(ratio_to_minimum); 114 Difference = max(estimate)-min(estimate) "
            "(dataset metric name “Abso”); 117 AVG(distance_from_best); 118 AVG(normalized). "
            "None have a subheader.",
            st["Body"],
        )
    )
    story.append(
        make_table(
            ["Chart", "ID", "Put this in Big Number → Subheader (Customize)"],
            [
                ["Difference (D)", "114", "Absolute gap: highest subgroup minus lowest subgroup"],
                ["Estimates", "112", "National / setting average of the selected indicator"],
                ["Ratio (R)", "113", "Highest subgroup divided by lowest subgroup (×)"],
                ["Absolute Concentration Index", "117", "Distance from the best-off group; 0 is equality"],
                ["Relative Concentration Index", "118", "Relative gap; 1 is the equity line on the scatter"],
            ],
            [W * 0.32, W * 0.10, W * 0.58],
            st,
        )
    )
    story.append(
        numbered(
            [
                "Open chart → Customize → Subheader (or “subtitle” on big_number_total) → paste the sentence → Save overwrite.",
                "Do not change the metric names unless 114’s label “Abso” bothers you — then rename the dataset metric to Difference (D) in Datasets → 29 → Metrics.",
            ],
            st,
        )
    )

    story.append(p("6.6 Triangulation tab (dashboard 3)", st["H2"]))
    story.append(
        p(
            "Saved chart 27 “EDHS vs DHIS2 for 2018” still exists (echarts bar, dataset "
            "5 edhs_dhis, metrics DHIS2 + EDHS, fiscal_year IN 2018, no indicator split). "
            "Live dashboard_slices does <b>not</b> place 27 on dashboard 3 or 8. Charts "
            "216, 217, 218 are already on dashboard 3, each filtered to one indicator.",
            st["Body"],
        )
    )
    story.append(
        numbered(
            [
                "Open dashboard 3 → Edit dashboard → open the Triangulation (or Multi-source) tab.",
                "Confirm 216 “% of Neonatal Deaths DHIS vs EDHS”, 217 “CAR DHIS vs EDHS”, 218 “Full Immunization Coverage DHIS vs EDHS” are visible.",
                "If chart 27 is on that tab, hover → delete from layout (does not delete the saved slice). If it is not on the tab, skip.",
                "Do not write a new query.",
            ],
            st,
        )
    )

    story.append(p("6.7 Empty-state copy (Handlebars / Big Number, no design)", st["H2"]))
    story.append(
        p(
            "Where a card still says “No data after filtering or data is NULL for the "
            "latest time record”, edit Customize → empty-state / markdown / Handlebars "
            "to: <b>No figure for this period. Latest available is the previous year.</b> "
            "Never print the word NULL on a Ministry screen. Apply at least to malaria "
            "97–101 and Summary 5 / 10 / 11.",
            st["Body"],
        )
    )

    # ------------------------------------------------------------------ WAVE 3
    story.append(PageBreak())
    story.append(p("7. Wave 3 — TV and theme (this repo, no design wait)", st["H"]))
    story.append(
        p(
            "One repository. The TV page is already in "
            "<font face='Courier'>superset/moh_assets.py</font> as the string _TV_PAGE, "
            "served at GET /moh-static/tv. Do not fork the project. Do this after Wave "
            "1–2. Deploy = commit + restart the Flask / gunicorn process that loads this "
            "module (no npm build required for these edits).",
            st["Body"],
        )
    )

    story.append(p("T3 — Stop shrinking the dashboard on the wall", st["H2"]))
    story.append(p("<b>Where:</b> superset/moh_assets.py → JavaScript function fit() inside _TV_PAGE", st["BodyLeft"]))
    story.append(
        p(
            "<b>What is wrong:</b> fit() sets scale s = viewportHeight / contentHeight, "
            "then iframe width = innerWidth / s, then transform: translate(...) scale(s), "
            "then multiplies s by 1.005. Authored 12px labels become 9–17px. That is why "
            "the wall looks unreadable even after Yengwe’s 22px tokens.",
            st["Body"],
        )
    )
    story.append(p("Replace the whole fit() body with 1:1 at 1920×1080 and letterbox:", st["Caption"]))
    story.append(
        sql_box(
            "function fit() {\n"
            "  const doc = safeDoc();\n"
            "  if (!doc || !doc.body) return;\n"
            "  unlockScroll(doc);\n"
            "  hideTabBars(doc);\n"
            "  wireIframeGestures();\n"
            "  wireResizeObserver(doc);\n"
            "  const vw = window.innerWidth;\n"
            "  const vh = window.innerHeight;\n"
            "  const DESIGN_W = 1920;\n"
            "  const DESIGN_H = 1080;\n"
            "  frame.style.width = DESIGN_W + 'px';\n"
            "  frame.style.height = DESIGN_H + 'px';\n"
            "  frame.style.transform = 'none';\n"
            "  frame.style.left = Math.max(0, (vw - DESIGN_W) / 2) + 'px';\n"
            "  frame.style.top = Math.max(0, (vh - DESIGN_H) / 2) + 'px';\n"
            "}\n",
            st,
            W,
        )
    )
    story.append(
        p(
            "Also delete the CSS comment above #tv that says the iframe is scaled to fit. "
            "Keep background #000 on html,body so unused edges letterbox. Remove the "
            "1.005 overshoot — it is in the current fit() just before transform.",
            st["Body"],
        )
    )
    story.append(
        p(
            "<b>Done when:</b> On a 1920×1080 panel, chart axis labels are the authored "
            "size (not 12px × a fraction). If the dashboard is taller than 1080, it "
            "clips — that is correct; author the dashboard to 1920×1080 instead of "
            "shrinking it. Laptop portal is unchanged.",
            st["Body"],
        )
    )

    story.append(p("T4 — Skip a slide that did not render", st["H2"]))
    story.append(p("<b>Where:</b> same file, functions run() / next() inside _TV_PAGE", st["BodyLeft"]))
    story.append(
        p(
            "<b>What is wrong:</b> next() always burns CFG.intervalMs (30–45s) even when "
            "the iframe is empty chrome or still showing -1.0 from a failed extract.",
            st["Body"],
        )
    )
    story.append(p("Add this helper next to contentHeight():", st["Caption"]))
    story.append(
        sql_box(
            "function slideLooksEmpty(doc) {\n"
            "  if (!doc) return true;\n"
            "  const nodes = doc.querySelectorAll(\n"
            "    'canvas, svg, .big_number, .deckgl-overlay, [data-test=\"chart-container\"]'\n"
            "  );\n"
            "  return nodes.length === 0;\n"
            "}\n",
            st,
            W,
        )
    )
    story.append(
        p(
            "At the end of run(), after clickPath succeeds, poll for up to 8 seconds. "
            "If still empty, call next() immediately instead of waiting for the interval. "
            "Guard with the existing token so overlapping slides do not race:",
            st["Body"],
        )
    )
    story.append(
        sql_box(
            "        if (await clickPath(CFG.slides[n].path, my) && my === token) {\n"
            "          scheduleFit();\n"
            "          const start = Date.now();\n"
            "          while (Date.now() - start < 8000 && my === token) {\n"
            "            if (!slideLooksEmpty(safeDoc())) break;\n"
            "            await sleep(400);\n"
            "          }\n"
            "          if (my === token && slideLooksEmpty(safeDoc())) next();\n"
            "        }\n",
            st,
            W,
        )
    )
    story.append(
        p(
            "<b>Done when:</b> A failed malaria extract no longer occupies a full "
            "rotation slot. A healthy slide still waits the configured interval.",
            st["Body"],
        )
    )

    story.append(CondPageBreak(50 * mm))
    story.append(p("T5 — Hide ASK AI on the TV page only", st["H2"]))
    story.append(p("<b>Where:</b> unlockScroll() injected CSS string in _TV_PAGE", st["BodyLeft"]))
    story.append(
        p(
            "Append to st.textContent (the long CSS already hiding #main-menu and tab bars). "
            "Laptop portal is not injected with this stylesheet, so ASK AI stays there.",
            st["Body"],
        )
    )
    story.append(
        sql_box(
            "'button[aria-label*=\"Ask AI\"], [class*=\"ask-ai\"],'\n"
            "+ '[class*=\"AskAI\"], .ant-float-btn {display:none!important;}';",
            st,
            W,
        )
    )
    story.append(
        p(
            "If the launcher still shows, Inspect inside the iframe for the 56×56 "
            "button at z-index 9999 and add that class to the same rule. This is CSS "
            "in the TV shell, not a product decision about Feedback.",
            st["Note"],
        )
    )
    story.append(
        p("<b>Done when:</b> TV slides have no overlapping ASK AI chip. Laptop still has it.", st["Body"]),
    )

    story.append(p("T6 — Do not apply 22px TV type to the laptop theme", st["H2"]))
    story.append(p("<b>Where:</b> the running superset_config.py THEME_DEFAULT (not Apache’s default in superset/config.py)", st["BodyLeft"]))
    story.append(
        p(
            "<b>What is wrong:</b> fontSize 22 and ECharts textStyle 24 sit on "
            "THEME_DEFAULT, so they hit every laptop user. The TV page does not need "
            "that once T3 is 1:1 — the dashboard is authored at wall size.",
            st["Body"],
        )
    )
    story.append(
        numbered(
            [
                "Open the config file the process actually loads (often /app/pythonpath/superset_config.py in Docker, or the host path you use for the 196.189.126.21 instance).",
                "If THEME_DEFAULT[\"token\"][\"fontSize\"] is 22, set it back to 14 (Apache default). Remove tv_size_* tokens from THEME_DEFAULT if they are there.",
                "If echartsOptionsOverrides sets fontSize 24 globally, delete that block from THEME_DEFAULT. Optionally keep a copy only for documentation; do not apply it to the laptop theme.",
                "Restart gunicorn / the Docker api container. Hard-refresh the laptop portal.",
            ],
            st,
        )
    )
    story.append(
        p(
            "<b>Done when:</b> Laptop Summary looks like Apache defaults (~12–14px). TV "
            "still gets large type from T3 (1:1) because the dashboard was authored for "
            "the wall, not because the laptop theme was inflated.",
            st["Body"],
        )
    )

    story.append(
        callout(
            "Restart after Wave 3",
            "moh_assets.py is Python. Saving the file is not enough. Restart the process "
            "that imported it. Then open /moh-static/tv in a 1920×1080 window (browser "
            "device mode is enough for a first pass) and walk Prev/Next through every slide.",
            st,
            W,
        )
    )

    # ------------------------------------------------------------------ checklist
    story.append(PageBreak())
    story.append(p("8. Day-by-day (one person can do all of it)", st["H"]))
    story.append(
        make_table(
            ["When", "Hours", "Work", "Exit ticket"],
            [
                [
                    "Day 1 morning",
                    "2–3",
                    "Backup SQL. T1 malaria. T2 woreda_region_map. Run both Check queries.",
                    "neg_risk = 0, neg_pct = 0, region rows still present.",
                ],
                [
                    "Day 1 afternoon",
                    "2–3",
                    "Malaria charts 97, 99, 100, 101, 102, 103, 104. Screenshot dashboard 8 malaria tab.",
                    "No -1.0, no 0-vs-No-data, legend not -1 – -1.",
                ],
                [
                    "Day 2 morning",
                    "2–3",
                    "Maps 74, 89, 161, 58, 95. Confirm is_descending on maternal deaths.",
                    "Darkest maternal colour = most deaths. No amber row-limit icon at national.",
                ],
                [
                    "Day 2 afternoon",
                    "2–3",
                    "PHEM 152–154. Summary 5/10/11. Equity subheaders. Triangulation 216–218. Empty-state copy.",
                    "CFR matches deaths/cases. Equity cards have one line under the number.",
                ],
                [
                    "Day 3",
                    "3–4",
                    "T3 fit(), T4 skip-blank, T5 ASK AI CSS, T6 laptop type. Restart. QA /moh-static/tv.",
                    "Labels readable at 3 m on 1920×1080. Laptop type unchanged. ASK AI absent on TV.",
                ],
            ],
            [W * 0.18, W * 0.10, W * 0.40, W * 0.32],
            st,
        )
    )

    story.append(p("9. Check list (screenshot after each wave)", st["H"]))
    story.append(
        make_table(
            ["#", "Check", "How", "Pass"],
            [
                ["1", "Malaria Average risk index is not -1.0 when extract is empty", "Dashboard 8, pick a climate/season with no rows", ""],
                ["2", "Malaria High-risk woredas is not 0 beside No data cards", "Same empty extract", ""],
                ["3", "Malaria map legend is not -1 – -1", "Chart 103", ""],
                ["4", "Maternal deaths map: darkest colour = most deaths; legend says worse", "Chart 74 tooltip vs colour", ""],
                ["5", "Woreda heatmap: no amber row-limit icon at national", "Chart 161 zoomed to Ethiopia", ""],
                ["6", "National CFR equals deaths / cases (× 1,000), not SUM of rates", "Charts 150, 151, 152 one disease-year", ""],
                ["7", "Equity cards have a one-line definition under the number", "Charts 112–118", ""],
                ["8", "Coverage &gt; 100% is footnoted or capped", "Chart 10 on an over-100 indicator", ""],
                ["9", "TV: labels readable at 3 metres; no scale-to-fit shrink", "/moh-static/tv at 1920×1080", ""],
                ["10", "Laptop: type size unchanged from before T6", "Dashboard 3 Summary", ""],
                ["11", "TV: ASK AI chip absent; laptop still has it", "Side by side", ""],
                ["12", "TV: blank slide does not eat a full 30–45s slot", "Force a bad tab or throttle network", ""],
            ],
            [W * 0.07, W * 0.38, W * 0.40, W * 0.15],
            st,
        )
    )

    story.append(p("10. Rollback", st["H"]))
    story.append(
        numbered(
            [
                "Datasets: Edit SQL → paste the backup file from section 4.1 → Save. Charts immediately see the old -1 again.",
                "Charts: Explore → you cannot diff easily. Re-set metric / filter / colour from the “Live now” column in this PDF, or restore from a dashboard export if you took one (Dashboards → ⋯ → Export before Wave 2).",
                "TV code: git checkout -- superset/moh_assets.py && restart. If T6 changed production config, put fontSize 22 back only if you must; prefer leaving laptop at 14.",
            ],
            st,
        )
    )

    story.append(
        KeepTogether(
            [
                p("11. Chart and dataset IDs (from live metadata)", st["H"]),
                make_table(
                    ["ID", "Name", "Used by"],
            [
                ["28", "malaria_risk_data (virtual SQL, ClickHouse moh)", "Charts 97–104"],
                ["53", "woreda_region_map (virtual SQL, ClickHouse moh)", "Charts 74, 89, 161"],
                ["1", "moh_meged_data", "Summary KPIs 5 / 10 / 11"],
                ["49", "phem", "Charts 150 / 151 / 152 / 153 / 154"],
                ["29 / 30", "Simple Measure / Disproportionality", "Charts 112–118"],
                ["5", "edhs_dhis", "Charts 27 (unused), 216 / 217 / 218"],
                ["18", "Quarterly_map_dataset", "Chart 58"],
                ["26", "TB Cases notified", "Chart 95"],
                ["8", "Inteligence dashboard (TV iframe target)", "dashboards.id"],
                ["3", "MOH Performance Monitering Dashboard (laptop)", "dashboards.id"],
            ],
            [W * 0.14, W * 0.44, W * 0.42],
                    st,
                ),
            ]
        )
    )

    story.append(PageBreak())
    story.append(p("12. Excel tracker — row by row", st["H"]))
    story.append(
        p(
            "Each row is one tracker Task ID. Mark CLOSES rows done on the Tasks sheet "
            "when the plan “Done when” is true. Leave PARTIAL rows TODO.",
            st["Body"],
        )
    )
    story.append(
        make_table(
            ["Plan", "Tracker", "Finding", "Status", "Cov.", "What this plan does"],
            [
                [r[0], r[3], r[4], r[7], r[8], r[10]]
                for r in ROWS
            ],
            [W * 0.08, W * 0.12, W * 0.10, W * 0.10, W * 0.12, W * 0.48],
            st,
        )
    )
    story.append(p("Tracker rows this plan does not start", st["H2"]))
    story.append(
        make_table(
            ["Tracker Task ID", "Finding", "Severity", "Title", "Why out"],
            OUT_OF_PLAN,
            [W * 0.18, W * 0.12, W * 0.12, W * 0.28, W * 0.30],
            st,
        )
    )

    story.append(p("13. Out of scope (do not start these in this plan)", st["H"]))
    story.append(
        bullets(
            [
                "Official emblems, footer wording, Amharic on dashboards.",
                "PHEM alert thresholds (need MoH / WHO numbers). Colour scheme change is in scope; invented lines are not.",
                "Custom React KPI card, Shepherd left-rail, Nobert traffic-light HTML.",
                "A second GitHub repository or a second ClickHouse copy for TV.",
                "Hatched polygon plugin — NULL + data_status filter is enough for this plan.",
                "Report Generator period header (custom app code, separate sprint).",
                "Filter state carrying between modules (plugin).",
                "Rewriting moh_meged_data (597 lines) or adding completeness strips that need a new grain — not required to stop -1.0 and inverted death maps.",
            ],
            st,
        )
    )

    story.append(
        p(
            "After Waves 1–3, the portal stops colouring deaths as coverage, stops "
            "printing -1.0 as a risk index, and the TV stops shrinking desktop layouts. "
            "Everything else can wait without blocking that result.",
            st["Body"],
        )
    )

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print("Wrote", OUT)


if __name__ == "__main__":
    build()
