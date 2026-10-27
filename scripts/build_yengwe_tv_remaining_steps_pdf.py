# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Build a step-by-step PDF for remaining Yengwe TV review work."""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = (
    "/home/zelalem/Desktop/UX_UI/Yengwe - TV viewport/Review result/"
    "HABTech_TV_Remaining_Steps.pdf"
)

NAVY = colors.HexColor("#1B365D")
TEAL = colors.HexColor("#0E6B7A")
INK = colors.HexColor("#1A1A1A")
MUTED = colors.HexColor("#4A5568")
RULE = colors.HexColor("#D6DEE8")
PALE = colors.HexColor("#F4F7FA")
ROW_ALT = colors.HexColor("#EEF3F7")
PALE_TEAL = colors.HexColor("#E7F2F4")
PALE_WARN = colors.HexColor("#FBF0DE")
WARN = colors.HexColor("#8F5D00")


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
            fontSize=20,
            leading=25,
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
        "MoH Analytics Portal  |  Yengwe TV remaining steps  |  Week 4",
    )
    canvas.setFillColor(RULE)
    canvas.rect(0, 0, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(
        16 * mm,
        5 * mm,
        "Review result  |  25 September 2026  |  repo-checked",
    )
    canvas.drawRightString(A4[0] - 16 * mm, 5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def p(text, style):
    return Paragraph(text, style)


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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


def code_box(text, st, width):
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


def callout(title, body, st, width, pale=PALE_TEAL, box=TEAL):
    inner = [
        Paragraph(f"<b>{title}</b>", st["H3"]),
        Paragraph(body, st["BodyLeft"]),
    ]
    t = Table([[inner]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), pale),
                ("BOX", (0, 0), (-1, -1), 0.5, box),
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
        title="Yengwe TV remaining steps — HABTech Week 4",
        author="HABTech / moh-superset",
    )
    story = []
    w = 178 * mm

    story.append(
        p("SYM-HABT-2026-09-001  ·  WEEK 4  ·  TV VIEWPORT  ·  HOW TO CLOSE IT", st["CoverKicker"])
    )
    story.append(p("Remaining TV tasks — every step", st["CoverTitle"]))
    story.append(
        p(
            "Companion to HABTech_TV_Developer_Worklist.docx and "
            "HABTech_TV_Rebuild_Review.docx. Those documents say what is wrong. "
            "This PDF says exactly what to change, in which file or portal screen, "
            "and how to know it is done. Checked against the moh-superset repo on "
            "25 September 2026.",
            st["CoverSub"],
        )
    )
    story.append(
        callout(
            "Do not confuse IDs",
            "Review TV-01 / TV-02 = native 1920 × 1080 (already done). "
            "Worklist TV-1 = raise chart text to 24 px (still open).",
            st,
            w,
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(
        make_table(
            ["Slice", "Where you work", "Items"],
            [
                [
                    "1 — Code / CSS / config",
                    "Git: moh-superset. Then recycle gunicorn.",
                    "TV-1, TV-2 binding, TV-3 fallback, TV-5, TV-10 chip, idle bar, TV-12",
                ],
                [
                    "2 — Portal / SQL",
                    "Dataset editor and Explore. Not in git.",
                    "TV-2 titles, TV-4, TV-6, TV-7, TV-8 copy, TV-9, TV-10 titles, TV-11",
                ],
                [
                    "3 — Blocked",
                    "Needs an analyst or INSA / Ministry.",
                    "TV-13 (CFR), TV-14 (Tableau + ASK AI sandbox)",
                ],
            ],
            [38 * mm, 70 * mm, 70 * mm],
            st,
        )
    )
    story.append(
        p(
            "No new required superset_config keys. Do not add MOH_TV_PERIOD_GREGORIAN. "
            "Optional only: MOH_TV_EMPTY_MARKERS, MOH_TV_SKIP_EMPTY_RATIO.",
            st["Note"],
        )
    )

    # ------------------------------------------------------------------ already done
    story.append(p("0. Already accepted — do not redo", st["H"]))
    story.append(
        p(
            "Yengwe re-measured these on 25 September and marked them resolved.",
            st["Body"],
        )
    )
    story.append(
        bullets(
            [
                "Native 1920 × 1080 canvas (review TV-01 / TV-02).",
                "Frame filled (Health Equity no longer leaves a white slab).",
                "Masthead: emblem, Ministry of Health, Service Delivery, fiscal year.",
                "Scope strip: Geography, Period, Source; freshness chip with status dot.",
                "Module accents and chips (MAL, HIV, TB, HE).",
                "Corrected inks #626B77, #14181D, #0374B8, #1E7A4C.",
                "Choropleth ramps single-hue (no red-to-green).",
                "HIV 95-95-95 KPI card pattern (unit + descriptor).",
                "ASK AI hidden on the wall TV; iframe title present; no camera / mic.",
                "Same-window TV login (no iframe Sign-in).",
            ],
            st,
        )
    )

    # ------------------------------------------------------------------ repo check
    story.append(p("1. What the repo still has open", st["H"]))
    story.append(
        p(
            "This table is from reading git, not from the review Word files. "
            "If a row says “not in repo”, the defect lives in the Superset metadata "
            "database (chart titles, virtual-dataset SQL, Explore params).",
            st["Body"],
        )
    )
    story.append(
        make_table(
            ["ID", "In git?", "Evidence"],
            [
                [
                    "TV-1",
                    "Yes — apply is late",
                    "default_tv_theme() already has 24 px. applyTheme() writes "
                    "localStorage after ThemeController.loadDevThemeOverride().",
                ],
                [
                    "TV-2 strip",
                    "Yes",
                    "loadFreshness() → applyYear() from /api/v1/moh/dhis2/data-freshness.",
                ],
                [
                    "TV-3",
                    "Yes",
                    "BigNumberViz.tsx: “No data after filtering or data is NULL "
                    "for the latest time record”.",
                ],
                [
                    "TV-5",
                    "Yes",
                    "injectCss(): strip keys 18 px, wordmark 19 px, titles 22 px.",
                ],
                [
                    "TV-8 slot",
                    "Yes — missing",
                    "_tv_slide_payload() has path, label, accent, source. No annotation.",
                ],
                [
                    "TV-10 chip",
                    "Yes",
                    "glyphText(“NCD - Screenings”) → N-.",
                ],
                [
                    "Idle bar",
                    "Yes",
                    "body.idle hides the cursor only. #mohTvControls stays visible.",
                ],
                [
                    "TV-12",
                    "Yes — incomplete",
                    "skipEmptyRatio 0.8. Markers: “No results…” and “No data” only.",
                ],
                [
                    "TV-14 Tableau",
                    "Yes",
                    "DashboardContainer.tsx embeds public.tableau.com on dashboard 8 PHC.",
                ],
                [
                    "TV-14 sandbox",
                    "Yes — missing",
                    "tail_js_custom_extra.html #mohAiIframe has title, no sandbox.",
                ],
                [
                    "TV-4, 6, 7, 9, 11, 13",
                    "Not in git",
                    "Chart / dataset metadata. Do these in the portal.",
                ],
            ],
            [28 * mm, 36 * mm, 114 * mm],
            st,
        )
    )

    # ------------------------------------------------------------------ files
    story.append(PageBreak())
    story.append(p("2. Slice 1 — files you will edit", st["H"]))
    story.append(
        make_table(
            ["File", "Why"],
            [
                [
                    "superset/templates/superset/moh_tv_player.js",
                    "Theme reload, Period from cards, NULL replace, CSS sizes, "
                    "glyphText, hide idle controls, skip-all-empty.",
                ],
                [
                    "superset/moh_assets.py",
                    "Default emptyMarkers; keep default_tv_theme() as-is (24 px already).",
                ],
                [
                    "superset/templates/tail_js_custom_extra.html",
                    "Cache-bust moh_tv_player.js?v=… after you change the player.",
                ],
                [
                    "superset_config.example.py",
                    "Comment-only: document MOH_TV_EMPTY_MARKERS extras. No new required keys.",
                ],
                [
                    "tests/unit_tests/moh_assets_tv_test.py",
                    "Assert theme 24 px still ships; assert emptyMarkers include NULL "
                    "and “No data after filtering”; assert player source contains the "
                    "new glyph / skip rules.",
                ],
            ],
            [62 * mm, 116 * mm],
            st,
        )
    )
    story.append(p("After every Slice 1 edit", st["H2"]))
    story.append(
        numbered(
            [
                "Save the files.",
                "Bump the player query string in tail_js_custom_extra.html "
                "(example: ?v=yengwe-slice1-1). Flask caches JS for a long time "
                "if you skip this.",
                "Recycle gunicorn (HUP is often not enough — kill/restart the workers "
                "so they reload templates).",
                "Hard-refresh /moh-static/tv/group/service-delivery (Ctrl+Shift+R).",
            ],
            st,
        )
    )

    # ------------------------------------------------------------------ TV-1
    story.append(p("3. TV-1 — Chart text 12 px → 24 px", st["H"]))
    story.append(
        p(
            "<b>Where:</b> moh_tv_player.js function applyTheme. "
            "Theme JSON is already correct in moh_assets.py default_tv_theme(). "
            "Do not invent a second theme. Do not assign a dashboard theme in "
            "Settings → Themes (that is the metadata DB).",
            st["Body"],
        )
    )
    story.append(p("Why it failed", st["H2"]))
    story.append(
        p(
            "ThemeController reads localStorage key superset-dev-theme-override "
            "in its constructor (loadDevThemeOverride). The TV player writes that "
            "key later. ECharts has already drawn at the platform 12 px.",
            st["Body"],
        )
    )
    story.append(p("Steps", st["H2"]))
    story.append(
        numbered(
            [
                "Open applyTheme() in moh_tv_player.js.",
                "Keep writing the theme JSON to localStorage['superset-dev-theme-override'].",
                "If sessionStorage.mohTvThemeApplied is missing: set it to '1' and "
                "call location.reload() once. The second boot reads the override.",
                "On pagehide, keep removing the theme key (already there) and also "
                "remove sessionStorage.mohTvThemeApplied so a later visit can re-apply.",
                "In injectCss() / unlockScroll(), add a backup only for non-ECharts "
                "text inside #mohTvStage: table cells, Handlebars, deck.gl HTML legend "
                "at font-size: 22px !important. Canvas labels still need the theme.",
            ],
            st,
        )
    )
    story.append(p("Sketch", st["H3"]))
    story.append(
        code_box(
            "function applyTheme(theme) {\n"
            "  if (!theme) return;\n"
            "  localStorage.setItem(THEME_KEY, JSON.stringify(theme));\n"
            "  if (!sessionStorage.getItem('mohTvThemeApplied')) {\n"
            "    sessionStorage.setItem('mohTvThemeApplied', '1');\n"
            "    location.reload();\n"
            "    return;\n"
            "  }\n"
            "  window.addEventListener('pagehide', function () {\n"
            "    localStorage.removeItem(THEME_KEY);\n"
            "    sessionStorage.removeItem('mohTvThemeApplied');\n"
            "  });\n"
            "}",
            st,
            w,
        )
    )
    story.append(
        p(
            "Done when: HIV or TB axis / legend is at least 22 px after one reload. "
            "Yengwe’s test: no canvas-drawn label below 22 px.",
            st["Note"],
        )
    )

    # ------------------------------------------------------------------ TV-2
    story.append(p("4. TV-2 — One calendar; strip agrees with cards", st["H"]))
    story.append(
        p(
            "Two halves. Only the strip binding is in git. Card titles that still "
            "say bare “2018” are Explore.",
            st["Body"],
        )
    )
    story.append(p("4a. Code — bind Period to the cards", st["H2"]))
    story.append(
        p(
            "<b>Where:</b> loadFreshness() and applyYear() in moh_tv_player.js. "
            "Today loadFreshness() calls applyYear(yearFromPeriod(period)) from "
            "the freshness API. That is why the strip can say 2019 EFY while "
            "cards say 2018.",
            st["Body"],
        )
    )
    story.append(
        numbered(
            [
                "Stop calling applyYear() from loadFreshness(). Freshness stays only "
                "on the green chip: “Data as of 2019 EFY · Meskerem”.",
                "Add yearFromCards(): query "
                ".dashboard-component-chart-holder .header-title and "
                "[data-test=editable-title]. Collect every /\\d{4}/. Count them. "
                "Return the most common year as “{year} EFY”.",
                "Call applyYear(yearFromCards()) after alignChartTitles() / settle(), "
                "once the slide’s titles are in the DOM.",
                "If no year is on the cards, leave #mohTvPeriod and #mohTvStripPeriod "
                "blank. Do not invent 2019. Do not put Gregorian back "
                "(no “2018 EFY (2025/26 GC)” unless product later asks).",
                "paintChrome() should keep calling applyYear(liveYear) so a slide "
                "change does not restore the freshness year.",
            ],
            st,
        )
    )
    story.append(p("4b. Portal — name the calendar on the cards", st["H2"]))
    story.append(
        numbered(
            [
                "Open each TV chart in Explore (Malaria, HIV, TB, NCD, PHEM, Health Equity).",
                "Chart title / subtitle: change bare “2018” to “2018 EFY”. "
                "Change “2017 EFY/ 2024” to “2017 EFY” only.",
                "Save. Repeat for every title Yengwe listed as bare year.",
                "If a filter message says “Period: 2018 · 2017 EFY”, fix that "
                "filter’s default label in the dashboard native filters.",
            ],
            st,
        )
    )
    story.append(
        p(
            "Done when: strip Period matches the cards (e.g. 2018 EFY). The chip "
            "may still say Data as of 2019 EFY · Meskerem. Every year on a card "
            "names EFY.",
            st["Note"],
        )
    )

    # ------------------------------------------------------------------ TV-3
    story.append(p("5. TV-3 — Take the NULL sentence off the screen", st["H"]))
    story.append(
        p(
            "<b>Source in git:</b> superset-frontend/plugins/plugin-chart-echarts/"
            "src/BigNumber/BigNumberViz.tsx — constant NO_DATA_OR_HASNT_LANDED. "
            "Changing that file also changes desktop. Slice 1 is TV-only.",
            st["Body"],
        )
    )
    story.append(p("5a. Code — TV DOM fallback", st["H2"]))
    story.append(
        numbered(
            [
                "After fit() / alignChartTitles(), walk visible "
                "[data-test=dashboard-component-chart-holder] nodes.",
                "If text contains “NULL” or “No data after filtering”, replace that "
                "text node with “No case data was returned for {period} EFY.” "
                "Use the year from yearFromCards() (TV-2).",
                "In moh_assets.py _tv_options(), add to default MOH_TV_EMPTY_MARKERS: "
                "“No data”, “NULL”, “No data after filtering”, “Not available”.",
            ],
            st,
        )
    )
    story.append(p("5b. Portal — permanent (optional later)", st["H2"]))
    story.append(
        p(
            "On each empty Big Number, set a subtitle in Explore so the chart "
            "never emits the NULL sentence. Or replace those cards with Handlebars. "
            "Do this after 5a if you want desktop cleaned too.",
            st["Body"],
        )
    )
    story.append(
        p(
            "Done when: the words NULL, “after filtering”, and “time record” "
            "appear nowhere in the TV rotation.",
            st["Note"],
        )
    )

    # ------------------------------------------------------------------ TV-5
    story.append(PageBreak())
    story.append(p("6. TV-5 — Raise four chrome roles to the 22 px floor", st["H"]))
    story.append(
        p(
            "<b>Where:</b> injectCss() and alignChartTitles() in moh_tv_player.js. "
            "These are sizes you already control.",
            st["Body"],
        )
    )
    story.append(
        make_table(
            ["Selector", "Now", "Set to"],
            [
                [".moh-tv-strip-k (GEOGRAPHY / PERIOD / SOURCE)", "18 px", "22 px"],
                ["#mohTvMast .w2 (Service Delivery)", "19 px", "22 px"],
                [
                    ".header-title and alignChartTitles() setImp font-size",
                    "22 px",
                    "24 px, one line + ellipsis",
                ],
                [
                    "NCD annotation / chart subtitle you can target",
                    "15 px (measured live)",
                    "26 px. If you cannot target it, fix the chart description in Explore.",
                ],
            ],
            [78 * mm, 40 * mm, 60 * mm],
            st,
        )
    )
    story.append(
        numbered(
            [
                "Change the four font-size values in the injectCss() string.",
                "Change setImp(title, 'font-size', '22px') to '24px'.",
                "Change the unlockScroll() CSS that also sets header-title to 22px.",
                "Leave #mohTvMast .c1 (mast year) at 23 px — already above the floor.",
            ],
            st,
        )
    )
    story.append(
        p(
            "Done when: nothing a viewer is expected to read in the chrome measures "
            "below 22 px.",
            st["Note"],
        )
    )

    # ------------------------------------------------------------------ TV-10
    story.append(p("7. TV-10 — Chip N- and idle presenter bar", st["H"]))
    story.append(p("7a. Chip text", st["H2"]))
    story.append(
        p(
            "<b>Where:</b> glyphText() in moh_tv_player.js. Today it splits on "
            "spaces and takes first letters, so “NCD - Screenings” becomes “N-”.",
            st["Body"],
        )
    )
    story.append(
        numbered(
            [
                "If the title contains “ - ”, take the token before the hyphen.",
                "If that token is a known module code (NCD, HIV, TB, PHEM, PHC, HE, MAL), "
                "return it uppercased.",
                "Else if there is one word, return the first 2–3 letters uppercased.",
                "Else return the first word’s first 2–3 letters, not the first letters "
                "of two words.",
                "In tests/unit_tests/moh_assets_tv_test.py, read the player file and "
                "assert the known-code list is present (or mirror glyphText in Python).",
            ],
            st,
        )
    )
    story.append(p("7b. Hide idle controls", st["H2"]))
    story.append(
        numbered(
            [
                "In injectCss(), add: body.moh-tv-active.idle #mohTvControls{display:none!important;}",
                "idleCursor() already toggles body.idle after 3 seconds of no mouse / key. "
                "Do not add a second timer.",
                "On mousemove / keydown / pointerdown the bar comes back with the cursor.",
            ],
            st,
        )
    )
    story.append(p("7c. Portal — truncated titles (not Slice 1 code)", st["H2"]))
    story.append(
        numbered(
            [
                "Open charts whose titles end in “…”. Example: “TSR among all forms &amp; "
                "Cure rate for bacteriologically conf…”.",
                "Shorten the title so it fits one line at 24 px on 1920 px.",
                "If the strip already shows the year, drop the year from the title.",
            ],
            st,
        )
    )
    story.append(
        p(
            "Done when: chip always shows NCD / HIV / TB / HE / MAL, never N-. "
            "Controls vanish after idle. No title truncates at 1920 px.",
            st["Note"],
        )
    )

    # ------------------------------------------------------------------ TV-12
    story.append(p("8. TV-12 — Empty slide must not hold a slot", st["H"]))
    story.append(
        p(
            "<b>Where:</b> slideState() and settle() inside the player string in "
            "moh_assets.py (the TV driver), plus emptyMarkers in _tv_options(). "
            "The player file also contains the same settle loop if you moved it "
            "there — keep them in sync.",
            st["Body"],
        )
    )
    story.append(
        numbered(
            [
                "In _tv_options(), set default emptyMarkers to: "
                "“No results were returned for this query”, “No data”, “NULL”, "
                "“No data after filtering”, “Not available”.",
                "In settle(), skip when every visible card is empty or error: "
                "st.total &gt; 0 AND (st.empty + st.error) === st.total. "
                "Keep the existing ratio check as well (skipEmptyRatio 0.8).",
                "Keep skipStreak &lt; slides.length - 1 so a fully empty rotation "
                "still shows one slide.",
                "Optional: document MOH_TV_EMPTY_MARKERS and MOH_TV_SKIP_EMPTY_RATIO "
                "in superset_config.example.py. Do not edit live superset_config.py "
                "unless you want custom markers.",
            ],
            st,
        )
    )
    story.append(
        p(
            "Done when: a Malaria slide whose every card is “No data” / error "
            "does not hold a full dwell. The rotation advances.",
            st["Note"],
        )
    )

    # ------------------------------------------------------------------ slice 2
    story.append(PageBreak())
    story.append(p("9. Slice 2 — portal / SQL (not in git)", st["H"]))
    story.append(
        p(
            "These defects are not in the moh-superset tree. Do them in the "
            "running portal. One dataset save updates laptop and TV.",
            st["Body"],
        )
    )

    story.append(p("TV-4 — High-risk woredas: 0 is not an all-clear", st["H2"]))
    story.append(
        numbered(
            [
                "Open the Malaria high-risk Big Number (previously chart 101) in Explore.",
                "Find the metric (often COUNT_DISTINCT(woreda_id) on an empty extract).",
                "In the dataset SQL or an adhoc metric, return NULL when nothing was "
                "counted: NULLIF(count, 0) or filter risk_category and drop sentinels "
                "before the count.",
                "On the card, reuse the HIV pattern: large “Not available”, descriptor "
                "“This is not zero — no case list was returned.”",
                "Save. Confirm the card no longer shows a bare 0 beside two “No data” cards.",
            ],
            st,
        )
    )

    story.append(p("TV-6 — Database column names off the screen", st["H2"]))
    story.append(
        p(
            "Yengwe saw: MAT_Contraceptive Acceptance Rate, indicator_name, category, "
            "value_pct, data_element, HIV_Clients, HIV_ART.",
            st["Body"],
        )
    )
    story.append(
        numbered(
            [
                "Datasets → open the dataset → Columns / Metrics.",
                "Set Verbose Name once per column / metric (plain English, no underscore prefix).",
                "Save. Every chart on that dataset inherits the label. Do not rename "
                "column-by-column on each chart unless a chart overrides the label.",
            ],
            st,
        )
    )

    story.append(p("TV-7 — Health Equity cards like HIV 95-95-95", st["H2"]))
    story.append(
        numbered(
            [
                "Open the HIV 95-95-95 cards. Note: unit in the title (e.g. 1st 95(%)), "
                "value, one-line descriptor (“PLHIV know their status”).",
                "Open Health Equity cards 0.72 / 0.49 / 7.32.",
                "Add unit, one-line definition, and which direction is good "
                "(“higher is better” or “lower is better”). Handlebars or Big Number "
                "subheader — same component as HIV, not a new widget.",
                "Fix truncating titles.",
            ],
            st,
        )
    )

    story.append(p("TV-8 — Annotation sentence on every slide", st["H2"]))
    story.append(
        numbered(
            [
                "Ask the indicator owner for one sentence per slide (what the chart shows). "
                "Do not invent the sentence.",
                "When copy exists: add an annotation field on each MOH_TV_GROUPS slide "
                "in superset_config.py, pass it through _tv_slide_payload(), and render "
                "a 26 px line under #mohTvSlideTitle in the player.",
                "Until then, leave the slot out. The NCD STEPS line is a source note, "
                "not a reading of the data — replace it when the owner writes a real one.",
            ],
            st,
        )
    )

    story.append(p("TV-9 — Legend says which direction is good", st["H2"]))
    story.append(
        numbered(
            [
                "On each choropleth in Explore, set a legend / subtitle: "
                "“More deaths — worse” or “Higher coverage — better”.",
                "In moh_tv_player.js CSS, give the legend box enough height that "
                "bands do not scroll off an unattended panel "
                "(overflow: visible; min-height large enough for all bands).",
            ],
            st,
        )
    )

    story.append(p("TV-11 — Sentinel -1 still on the colour scale", st["H2"]))
    story.append(
        numbered(
            [
                "Open the virtual dataset behind the map whose legend reads “-1 – 3”.",
                "Map negative sentinels to NULL (do not emit toFloat64(-1) for missing).",
                "Keep a data_status or completeness column so the card can say "
                "how many units reported.",
                "Save dataset. Re-query the chart. Legend lowest band must not be -1.",
            ],
            st,
        )
    )

    # ------------------------------------------------------------------ blocked
    story.append(p("10. Blocked — do not guess", st["H"]))
    story.append(
        callout(
            "TV-13 — PHEM CFR",
            "Card still reads 6.8 with no unit against 343 deaths. "
            "343 ÷ 43,775 = 7.8 per 1,000. One of those three numbers is wrong. "
            "HABTech analysts decide. Do not change the metric until they say which.",
            st,
            w,
            pale=PALE_WARN,
            box=WARN,
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        callout(
            "TV-14 — Tableau embed and ASK AI sandbox",
            "Dashboard 8 PHC tab still iframes "
            "https://public.tableau.com/views/PHCDashboard2026/EthiopiaPHCDashboard2026. "
            "Leave it until INSA / Ministry. ASK AI iframe has title and no allow "
            "(camera / mic already off) but no sandbox attribute. Add sandbox only "
            "if they approve. TV already hides ASK AI.",
            st,
            w,
            pale=PALE_WARN,
            box=WARN,
        )
    )

    # ------------------------------------------------------------------ verify
    story.append(p("11. Acceptance pass (one rotation at 1920 × 1080)", st["H"]))
    story.append(
        make_table(
            ["#", "Look for", "Closes"],
            [
                ["1", "No readable text below 22 px, chart labels included", "TV-1, TV-5"],
                ["2", "Every year names EFY; strip Period matches the cards", "TV-2"],
                ["3", "NULL / “after filtering” / “time record” nowhere", "TV-3"],
                ["4", "No numeral from an empty result (no high-risk 0)", "TV-4"],
                ["5", "No underscore-cased field name", "TV-6"],
                ["6", "Every headline number has unit, definition, direction", "TV-7"],
                ["7", "Every slide has one owner-signed annotation", "TV-8"],
                ["8", "Every choropleth states direction of good; all bands visible", "TV-9"],
                ["9", "No title truncates; year once per card; chip is NCD not N-", "TV-10"],
                ["10", "All-empty slide does not hold a full slot", "TV-12"],
                ["11", "Controls hide after the cursor is idle", "Idle bar"],
            ],
            [12 * mm, 118 * mm, 48 * mm],
            st,
        )
    )

    story.append(p("12. Suggested order of work", st["H"]))
    story.append(
        numbered(
            [
                "Slice 1 in one sitting: TV-5 CSS, TV-10 chip + idle, TV-3 replace, "
                "TV-2 yearFromCards, TV-12 markers + all-empty skip, TV-1 reload. "
                "Bump ?v=, recycle gunicorn, hard-refresh.",
                "Walk the acceptance rows 1, 2, 3, 9 (chip), 10, 11 on the live TV.",
                "Portal morning: TV-6 labels, TV-2 title EFY, TV-10 shorten titles, TV-9 legends.",
                "Dataset afternoon: TV-4 high-risk NULL, TV-11 sentinel NULL.",
                "TV-7 Health Equity cards (copy HIV).",
                "Park TV-8 until analysts write sentences. Park TV-13 / TV-14.",
            ],
            st,
        )
    )
    story.append(
        p(
            "Org-unit tree (prod vs localhost) is a separate deploy of "
            "superset/moh_orgunits_api.py. It is not a Yengwe TV ticket.",
            st["Note"],
        )
    )

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUT)


if __name__ == "__main__":
    build()
