"""Build the MetaLens Metadata Intelligence pitch deck as a clean PDF."""
from fpdf import FPDF

# Brand palette (matches the MetaLens retro theme)
CREAM = (242, 232, 208)
INK = (51, 38, 29)
MUTED = (138, 115, 88)
ORANGE = (196, 85, 26)
ORANGE_D = (156, 61, 14)
TEAL = (15, 118, 110)
GREEN = (63, 125, 63)
LIGHT_ORANGE = (247, 224, 200)
LIGHT_TEAL = (214, 233, 229)
CARD = (255, 252, 240)
WHITE = (255, 255, 255)

PAGE_W = 297
PAGE_H = 210


class Deck(FPDF):
    def __init__(self):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(False)

    def _brand_bar(self, slide_no: int, total: int = 10):
        self.set_fill_color(*CREAM)
        self.rect(0, 0, PAGE_W, PAGE_H, "F")
        # top brand strip
        self.set_fill_color(*ORANGE)
        self.rect(0, 0, PAGE_W, 4, "F")
        # wordmark + slide number
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*ORANGE)
        self.set_xy(12, 10)
        self.cell(0, 8, "MetaLens", ln=False)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*MUTED)
        self.set_xy(PAGE_W - 30, 10)
        self.cell(18, 8, f"{slide_no:02d} / {total}", align="R")

    def _footer(self):
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.set_xy(12, PAGE_H - 12)
        self.cell(0, 6, "MetaLens - Metadata Intelligence Pitch Deck")

    def slide_title(self, title: str, subtitle: str):
        self.set_y(24)
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(*INK)
        self.multi_cell(PAGE_W - 24, 12, title, ln=True)
        self.set_font("Helvetica", "", 13)
        self.set_text_color(*ORANGE_D)
        self.multi_cell(PAGE_W - 24, 7, subtitle, ln=True)

    def block(self, x, y, w, h, title, lines, accent=TEAL):
        self.set_fill_color(*CARD)
        self.set_draw_color(*accent)
        self.set_line_width(0.6)
        self.rect(x, y, w, h, "DF")
        self.set_fill_color(*accent)
        self.rect(x, y, 2.4, h, "F")
        self.set_xy(x + 5, y + 3)
        self.set_font("Helvetica", "B", 11.5)
        self.set_text_color(*INK)
        self.cell(w - 10, 6, title, ln=True)
        self.set_xy(x + 5, y + 11)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 50, 40)
        for ln in lines:
            self.set_x(x + 5)
            self.cell(w - 10, 5.6, ln)
            self.ln(5.6)

    def flow(self, y, items, x0=16, gap=16):
        """Horizontal arrow pipeline."""
        n = len(items)
        avail = PAGE_W - 2 * x0
        seg = avail / n
        for i, it in enumerate(items):
            x = x0 + i * seg
            self.set_fill_color(*LIGHT_TEAL)
            self.set_draw_color(*TEAL)
            self.rect(x, y, seg - gap, 26, "DF")
            self.set_xy(x + 3, y + 3)
            self.set_font("Helvetica", "B", 10.5)
            self.set_text_color(*INK)
            self.multi_cell(seg - gap - 6, 5.5, it, align="C")


pdf = Deck()

# ---------------------------------------------------------------- Cover
pdf.add_page()
pdf.set_fill_color(*CREAM)
pdf.rect(0, 0, PAGE_W, PAGE_H, "F")
pdf.set_fill_color(*ORANGE)
pdf.rect(0, 0, PAGE_W, 8, "F")
pdf.set_fill_color(*ORANGE)
pdf.rect(PAGE_W / 2 - 34, 58, 68, 68, "F")
pdf.set_font("Helvetica", "B", 30)
pdf.set_text_color(*WHITE)
pdf.set_xy(PAGE_W / 2 - 34, 78)
pdf.cell(68, 12, "MetaLens", align="C")
pdf.set_xy(PAGE_W / 2 - 34, 92)
pdf.set_font("Helvetica", "", 11)
pdf.cell(68, 8, "metadata intelligence", align="C")
pdf.set_y(142)
pdf.set_font("Helvetica", "B", 30)
pdf.set_text_color(*INK)
pdf.cell(PAGE_W, 14, "Metadata Intelligence Pitch Deck", align="C", ln=True)
pdf.set_y(160)
pdf.set_font("Helvetica", "", 13)
pdf.set_text_color(*ORANGE_D)
pdf.cell(PAGE_W, 8, "Capture  ·  Understand  ·  Enrich  ·  Publish", align="C")

# ---------------------------------------------------------------- 1. Problem
pdf.add_page()
pdf._brand_bar(1)
pdf.slide_title("The Problem", "Our most valuable metadata is trapped")
cols = [
    ("Teams", "Discussions, meeting notes"),
    ("Slack", "Conversations, shared files"),
    ("Spreadsheets", "Excel, CSV files"),
    ("Emails", "Decisions, clarifications"),
    ("Documents", "PDF, PPT, Word, Notion, Wikis"),
    ("Jira / Confluence", "Requirements, design docs"),
    ("Audio / Video", "Meetings, webinars, training videos"),
    ("Other sources", "Chat, tickets, intranet"),
]
cw = (PAGE_W - 32) / 4
ch = 44
for i, (name, desc) in enumerate(cols):
    r, c = divmod(i, 4)
    x = 16 + c * cw
    y = 70 + r * (ch + 8)
    pdf.set_fill_color(*LIGHT_ORANGE)
    pdf.set_draw_color(*ORANGE)
    pdf.rect(x, y, cw - 8, ch, "DF")
    pdf.set_xy(x + 4, y + 5)
    pdf.set_font("Helvetica", "B", 11.5)
    pdf.set_text_color(*INK)
    pdf.cell(cw - 16, 6, name)
    pdf.set_xy(x + 4, y + 14)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(60, 50, 40)
    pdf.multi_cell(cw - 16, 5, desc)
pdf.set_fill_color(*ORANGE)
pdf.rect(16, 172, PAGE_W - 32, 22, "F")
pdf.set_xy(22, 178)
pdf.set_font("Helvetica", "B", 12)
pdf.set_text_color(*WHITE)
pdf.cell(PAGE_W - 44, 8, "Rich business knowledge exists - but it never reaches your metadata platforms.")
pdf._footer()

# ---------------------------------------------------------------- 2. Signals
pdf.add_page()
pdf._brand_bar(2)
pdf.slide_title("What are Metadata Signals?", "Valuable information about data, hidden in everyday content")
pdf.flow(72, ["Source Content (raw)", "Extracted Signal", "Mapped to Data Asset (table / column)"])
pdf.block(16, 108, PAGE_W - 32, 44,
          "Example 1 - definition",
          ['"Inactive customer means no transaction for 90 days."',
           "-> Definition of inactive customer",
           "-> crm.customer.customer_status"], accent=ORANGE)
pdf.block(16, 158, PAGE_W - 32, 40,
          "Example 2 - business rule",
          ['"VIP customer: revenue > AED 100K (last 12 months)"',
           "-> Business rule",
           "-> sales.customer.customer_segment"], accent=TEAL)
pdf._footer()

# ---------------------------------------------------------------- 3. Gap
pdf.add_page()
pdf._brand_bar(3)
pdf.slide_title("The Gap", "Metadata platforms don't see the full picture")
pdf.block(16, 66, (PAGE_W - 36) / 2, 132,
          "What existing tools are good at",
          ["(Technical Metadata)",
           "",
           "· Schemas & lineage",
           "· Data quality & completeness",
           "· Usage & query history",
           "· Ownership & governance"], accent=TEAL)
pdf.block((PAGE_W - 36) / 2 + 20, 66, (PAGE_W - 36) / 2, 132,
          "What's missing",
          ["(Business Knowledge)",
           "",
           "· Business definitions",
           "· Operational rules",
           "· SME knowledge & decisions",
           "· Terminology & synonyms",
           "· Context from real conversations",
           "· Exceptions & special cases"], accent=ORANGE)
pdf._footer()

# ---------------------------------------------------------------- 4. Intro
pdf.add_page()
pdf._brand_bar(4)
pdf.slide_title("Introducing MetaLens", "Turn enterprise knowledge into metadata-ready signals")
pdf.set_y(66)
pdf.set_font("Helvetica", "B", 16)
pdf.set_text_color(*INK)
pdf.cell(PAGE_W, 10, "Capture  ·  Understand  ·  Enrich  ·  Publish", align="C", ln=True)
pdf.flow(86, ["Collect signals", "Understand content", "Map to data assets", "Structure metadata", "Publish to tools"])
pdf.set_fill_color(*LIGHT_TEAL)
pdf.rect(16, 150, PAGE_W - 32, 44, "DF")
pdf.set_xy(22, 156)
pdf.set_font("Helvetica", "B", 11.5)
pdf.set_text_color(*INK)
pdf.cell(PAGE_W - 44, 7, "Complements your existing metadata platform")
pdf.set_xy(22, 166)
pdf.set_font("Helvetica", "", 11)
pdf.set_text_color(60, 50, 40)
pdf.cell(PAGE_W - 44, 7, "Works with OpenMetadata, Collibra, Atlan, Purview and others.")
pdf._footer()

# ---------------------------------------------------------------- 5. How it works
pdf.add_page()
pdf._brand_bar(5)
pdf.slide_title("How it Works", "From a conversation to a trusted column description")
steps = [
    ("1", "Source Content", "Teams meeting transcript"),
    ("2", "AI Extraction", "Extract key information"),
    ("3", "Asset Mapping", "Map to table / column"),
    ("4", "Metadata Output", "Publish to catalog"),
]
for i, (num, t, d) in enumerate(steps):
    x = 16 + i * ((PAGE_W - 32) / 4)
    pdf.set_fill_color(*CARD)
    pdf.set_draw_color(*ORANGE)
    pdf.rect(x, 90, (PAGE_W - 32) / 4 - 10, 64, "DF")
    pdf.set_fill_color(*ORANGE)
    pdf.set_xy(x, 90)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*WHITE)
    pdf.cell(16, 14, num, align="C")
    pdf.set_xy(x + 4, 112)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*INK)
    pdf.multi_cell((PAGE_W - 32) / 4 - 18, 6, t)
    pdf.set_x(x + 4)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(60, 50, 40)
    pdf.multi_cell((PAGE_W - 32) / 4 - 18, 5, d)
    if i < 3:
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*TEAL)
        pdf.set_xy(x + (PAGE_W - 32) / 4 - 8, 112)
        pdf.cell(8, 10, "->")
pdf._footer()

# ---------------------------------------------------------------- 6. Architecture
pdf.add_page()
pdf._brand_bar(6)
pdf.slide_title("Solution Architecture", "Metadata Signal Intelligence Layer")
pipe = [
    "Enterprise Knowledge Sources\nTeams · Spreadsheets · Documents · Emails / Jira / Confluence",
    "Ingestion & Connectors",
    "AI Processing & Entity Extraction",
    "Asset Mapping & Metadata",
    "Validation & Evidence",
    "Generation",
    "Metadata Platforms\nOpenMetadata · Collibra · Atlan · Purview · Others",
]
n = len(pipe)
seg = (PAGE_W - 32) / n
for i, p in enumerate(pipe):
    x = 16 + i * seg
    color = TEAL if i in (0, n - 1) else ORANGE
    fill = LIGHT_TEAL if i in (0, n - 1) else LIGHT_ORANGE
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*color)
    pdf.rect(x, 76, seg - 5, 56, "DF")
    pdf.set_xy(x + 3, 82)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*INK)
    pdf.multi_cell(seg - 11, 5, p, align="C")
    if i < n - 1:
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(x + seg - 4, 98)
        pdf.cell(5, 8, "->")
pdf.set_fill_color(*ORANGE)
pdf.rect(16, 160, PAGE_W - 32, 26, "F")
pdf.set_xy(22, 168)
pdf.set_font("Helvetica", "B", 12)
pdf.set_text_color(*WHITE)
pdf.cell(PAGE_W - 44, 8, "Both technical metadata and business knowledge are needed for complete enterprise context.")
pdf._footer()

# ---------------------------------------------------------------- 7. Trust
pdf.add_page()
pdf._brand_bar(7)
pdf.slide_title("Trust, Not Just AI Generation", "Every metadata signal comes with evidence and confidence")
pdf.block(16, 64, PAGE_W - 32, 74,
          "Example: Generated Column Description",
          ["Column   crm.customer.customer_status",
           'Description   "Inactive customer means a customer who has not completed a transaction in 90 days."',
           "Confidence   94%",
           "Source   Teams meeting - Customer Review",
           "Generated by MetaLens (LLM)  ·  Approved by Data Steward  ·  v1.0"], accent=ORANGE)
pdf.block(16, 148, (PAGE_W - 36) / 2, 50,
          "Human-in-the-loop",
          ["· Human review for critical metadata",
           "· Access control & security"], accent=TEAL)
pdf.block((PAGE_W - 36) / 2 + 20, 148, (PAGE_W - 36) / 2, 50,
          "Provenance",
          ["· Source evidence attached to every signal",
           "· Version history for every change"], accent=ORANGE)
pdf._footer()

# ---------------------------------------------------------------- 8. Result
pdf.add_page()
pdf._brand_bar(8)
pdf.slide_title("The Result", "A richer context layer for humans and AI")
pdf.set_fill_color(*LIGHT_ORANGE)
pdf.rect(PAGE_W / 2 - 40, 68, 80, 44, "DF")
pdf.set_xy(PAGE_W / 2 - 40, 76)
pdf.set_font("Helvetica", "B", 26)
pdf.set_text_color(*ORANGE)
pdf.cell(80, 14, "94%", align="C")
pdf.set_xy(PAGE_W / 2 - 40, 96)
pdf.set_font("Helvetica", "", 11)
pdf.set_text_color(*INK)
pdf.cell(80, 8, "signal confidence", align="C")
benefits = [
    "Power better analytics & AI use cases",
    "More accurate answers",
    "Better compliance",
    "Time saved for data stewards",
    "Accepted descriptions",
    "Improved data-asset accuracy",
]
cw = (PAGE_W - 32) / 3
for i, b in enumerate(benefits):
    r, c = divmod(i, 3)
    x = 16 + c * cw
    y = 124 + r * 40
    pdf.set_fill_color(*LIGHT_TEAL)
    pdf.rect(x, y, cw - 10, 32, "DF")
    pdf.set_xy(x + 4, y + 6)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*INK)
    pdf.multi_cell(cw - 18, 5.5, b)
pdf._footer()

# ---------------------------------------------------------------- 9. Use cases
pdf.add_page()
pdf._brand_bar(9)
pdf.slide_title("Use Cases", "Applicable across many domains and data types")
blocks = [
    ("Domain Knowledge", ["Industry terminology", "Product & customer context"], ORANGE),
    ("Cross-functional Knowledge", ["Clarifications from Slack / Email", "Decisions from meetings", "Reporting exceptions"], TEAL),
    ("Business Definitions", ["Business glossary terms", "KPI definitions & formulas", "Table / column descriptions"], ORANGE),
    ("Rules & Processes", ["Data usage rules", "Calculation logic"], TEAL),
    ("Consumers", ["Business Users", "Analysts / BI", "Data Consumers", "AI Agents / Copilots"], GREEN),
]
positions = [
    (16, 66, (PAGE_W - 44) / 3, 62), (16 + (PAGE_W - 44) / 3 + 11, 66, (PAGE_W - 44) / 3, 62),
    (16 + 2 * ((PAGE_W - 44) / 3 + 11), 66, (PAGE_W - 44) / 3, 62),
    (16, 134, (PAGE_W - 44) / 2, 62), (16 + (PAGE_W - 44) / 2 + 12, 134, (PAGE_W - 44) / 2, 62),
]
for (title, lines, color), (x, y, w, h) in zip(blocks, positions):
    pdf.block(x, y, w, h, title, ["· " + l for l in lines], accent=color)
pdf._footer()

# ---------------------------------------------------------------- 10. Next steps
pdf.add_page()
pdf._brand_bar(10)
pdf.slide_title("Next Steps", "Start small, prove value, then scale")
steps = [
    ("1", "Pilot", "One domain (Sales or Finance) · connect Teams & documents · publish to OpenMetadata"),
    ("2", "Measure Impact", "Signals discovered · steward time saved · accepted descriptions"),
    ("3", "Expand", "More domains · more sources · more metadata platforms"),
    ("4", "Long-term Vision", "Continuous enrichment · data meaning from SMEs · multi-platform support"),
]
for i, (num, t, d) in enumerate(steps):
    y = 66 + i * 36
    pdf.set_fill_color(*CARD)
    pdf.set_draw_color(*ORANGE)
    pdf.rect(16, y, PAGE_W - 32, 30, "DF")
    pdf.set_fill_color(*ORANGE)
    pdf.rect(16, y, 14, 30, "F")
    pdf.set_xy(16, y + 8)
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*WHITE)
    pdf.cell(14, 10, num, align="C")
    pdf.set_xy(36, y + 4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*INK)
    pdf.cell(40, 8, t)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(60, 50, 40)
    pdf.set_x(80)
    pdf.cell(PAGE_W - 96, 8, d)
pdf._footer()

out = "/Users/faisal.kattil_1/Desktop/openM/MetaLens Metadata Intelligence Pitch Deck.pdf"
pdf.output(out)
print("WROTE", out)
