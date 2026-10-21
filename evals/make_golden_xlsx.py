"""Build evals/golden_50_labels.xlsx from evals/golden_50_labels.csv: same rows and columns, label cells blank,
with dropdowns. No labels are written or suggested; the example on the Definitions tab is a made-up review,
not one of the 50.

  python evals/make_golden_xlsx.py
"""
import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evals" / "golden_50_labels.csv"
OUT = ROOT / "evals" / "golden_50_labels.xlsx"
TOPICS = ["access", "usability", "playback", "downloads", "catalog", "billing", "support", "other"]
INTENTS = ["cancellation", "complaint", "request", "praise", "unclear"]
LABEL_COLS = ["topic", "intent", "severity", "sentiment", "entities", "evidence_quote", "needs_review", "ambiguous",
              "accepted_alternatives", "notes"]
FONT = "Arial"
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")  # cells for Jack to fill
HEAD_FILL = PatternFill("solid", fgColor="D9D9D9")


def main():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig", newline="")))
    cols = list(rows[0].keys())
    assert all(not r[c].strip() for r in rows for c in LABEL_COLS), "label columns must be blank"
    wb = Workbook()
    ws = wb.active
    ws.title = "Labels"
    ws.append(cols)
    for r in rows:
        ws.append([int(r[c]) if c == "review_rating" and r[c].strip().isdigit() else r[c] for c in cols])
    n = len(rows) + 1
    widths = {"review_id": 38, "review_text": 70, "review_rating": 8, "topic": 13, "intent": 14, "severity": 9,
              "sentiment": 10, "entities": 22, "evidence_quote": 40, "needs_review": 13, "ambiguous": 11,
              "accepted_alternatives": 28, "notes": 30}
    letter = {c: ws.cell(row=1, column=i + 1).column_letter for i, c in enumerate(cols)}
    for c, w in widths.items():
        ws.column_dimensions[letter[c]].width = w
    for cell in ws[1]:
        cell.font = Font(name=FONT, bold=True)
        cell.fill = HEAD_FILL
    for row in ws.iter_rows(min_row=2, max_row=n):
        for cell in row:
            cell.font = Font(name=FONT)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if ws.cell(row=1, column=cell.column).value in LABEL_COLS:
                cell.fill = INPUT_FILL
    ws.freeze_panes = "B2"

    def dv_list(col, values, prompt):
        dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True,
                            showErrorMessage=True, errorTitle="Not a valid label", error="Pick from the list.",
                            showInputMessage=True, promptTitle=col, prompt=prompt)
        dv.add(f"{letter[col]}2:{letter[col]}{n}")
        ws.add_data_validation(dv)

    dv_list("topic", TOPICS, "One primary topic (see Definitions tab).")
    dv_list("intent", INTENTS, "Precedence: cancellation > complaint > request > praise > unclear.")
    dv_list("severity", ["1", "2", "3", "4", "5"], "1 no problem ... 5 serious financial/privacy/data harm.")
    dv_list("needs_review", ["TRUE", "FALSE"], "TRUE if context is missing or the call is close.")
    dv_list("ambiguous", ["TRUE", "FALSE"], "TRUE if more than one label is defensible.")
    sent = DataValidation(type="decimal", operator="between", formula1="-1", formula2="1", allow_blank=True,
                          showErrorMessage=True, error="Sentiment must be between -1 and 1.",
                          showInputMessage=True, promptTitle="sentiment", prompt="-1.0 (very negative) to 1.0 (very positive).")
    sent.add(f"{letter['sentiment']}2:{letter['sentiment']}{n}")
    ws.add_data_validation(sent)

    d = wb.create_sheet("Definitions")
    lines = [
        ("How to use", ""),
        ("Fill only the yellow cells on the Labels tab.", "Dropdowns: topic, intent, severity, needs_review, ambiguous. Sentiment accepts -1 to 1."),
        ("entities", "Feature terms the text explicitly names, separated by ';' (blank if none)."),
        ("evidence_quote", "Copy an exact substring of review_text that supports the label."),
        ("accepted_alternatives", "Optional, e.g. topic=billing|usability; severity=2|3"),
        ("Save", "Keep this file as .xlsx; python -m pipeline eval golden reads it directly."),
        ("", ""),
        ("Example format (made-up review, NOT one of the 50)", ""),
        ("review_text", "The app logs me out every morning and I can't get back in with my password."),
        ("labels", "topic=access; intent=complaint; severity=4; sentiment=-0.7; entities=login;password; "
                   "evidence_quote=I can't get back in with my password; needs_review=FALSE; ambiguous=FALSE"),
        ("", ""),
        ("topic", "Definition (GRADING_CONTRACT.md)"),
        ("access", "Login, signup, password or account access"),
        ("usability", "Navigation, controls, layout, queue/playlist management, ad interruptions"),
        ("playback", "Playback failure, crashes, lag, connection failures, audio quality, resource use"),
        ("downloads", "Downloading, saved music, offline listening, disappearing downloads"),
        ("catalog", "Missing songs/artists, search/discovery, recommendations, lyrics availability"),
        ("billing", "Price, charges, subscriptions, paywalls, premium entitlement; explicitly premium-only controls go here"),
        ("support", "Contacting support and the support response"),
        ("other", "General praise/criticism, unrelated content, or no supported specific topic"),
        ("Topic tie rules", "Highest supported severity; on a tie, the first specific problem. Positive review: first specific "
                            "praised feature; general praise is other. A paid-plan mention alone is not billing."),
        ("", ""),
        ("intent", "cancellation (explicitly leaving, uninstalling, cancelling, or threatening to) > complaint (negative "
                   "experience, incl. mixed) > request (desired change, no reported failure) > praise > unclear. Bare "
                   "boycott slogans and meaningless text are unclear. General 'bad app' is a complaint."),
        ("", ""),
        ("severity", "Meaning"),
        ("1", "No reported problem: praise, neutral/unclear content, or a pure feature request"),
        ("2", "Dislike, generic criticism, minor annoyance, or cosmetic issue; no supported functional loss"),
        ("3", "A degraded or restricted function; some use or workaround remains"),
        ("4", "A clearly blocked core task, such as inability to log in or play music"),
        ("5", "Explicit serious financial, privacy, or data harm; an expensive plan, a crash, or angry language alone is insufficient"),
        ("Note", "Cancellation intent does not raise severity. Missing context -> needs_review; do not invent impact."),
    ]
    for a, b in lines:
        d.append([a, b])
    d.column_dimensions["A"].width = 34
    d.column_dimensions["B"].width = 110
    for row in d.iter_rows():
        for cell in row:
            cell.font = Font(name=FONT, bold=cell.column == 1 and bool(cell.value))
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rows, label cells blank")


if __name__ == "__main__":
    main()
