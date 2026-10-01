"""
Builds a reusable lot dataset for the Streamlit app by matching:
  - jevnotes(Sheet2).csv  -> LTLOTNBR (lot number) to LTSLRNBR (seller code) + lot stage/status
  - Instructions(Sheet1).csv -> slr_cd (seller code) to that seller's standing instructions
  - jevnotes(Sheet1).csv  -> App Cde (lot number) to that lot's raw note history

...into one JSON file (lots_dataset.json) of ready-to-paste free text per lot,
grouped by seller code, so the Streamlit UI can offer a
"pick seller code -> pick lot -> auto-fill" selector instead of manual copy/paste.

Run this again whenever the source CSVs change:
    python3 build_dataset.py
"""

import csv
import json
import os

DOWNLOADS = os.path.expanduser("~/Downloads")
INSTRUCTIONS_CSV = os.path.join(DOWNLOADS, "Instructions(Sheet1).csv")
JEVNOTES_SHEET1_CSV = os.path.join(DOWNLOADS, "jevnotes(Sheet1).csv")
JEVNOTES_SHEET2_CSV = os.path.join(DOWNLOADS, "jevnotes(Sheet2).csv")

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lots_dataset.json")
STATS_OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset_stats.json")

NOTE_FIELD_LABELS = {
    "assgn_notes": "ASSIGNMENT NOTES",
    "biln_notes": "BILLING NOTES",
    "dspch_notes": "DISPATCH NOTES",
    "title_notes": "TITLE NOTES",
}
FIELD_ORDER = ["assgn_notes", "biln_notes", "dspch_notes", "title_notes"]


def load_instructions():
    """Returns {slr_cd: {"slr_comp_cd", "slr_nm", "fields": {key1: value1}}}"""
    sellers = {}
    with open(INSTRUCTIONS_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            slr_cd = row["slr_cd"].strip()
            sellers.setdefault(
                slr_cd,
                {
                    "slr_comp_cd": row["slr_comp_cd"].strip(),
                    "slr_nm": row["slr_nm"].strip(),
                    "fields": {},
                },
            )
            sellers[slr_cd]["fields"][row["key1"].strip()] = row["value1"].strip()
    return sellers


def load_lot_seller_map():
    """Returns {lot_number: {"slr_cd", "stage", "status"}}"""
    lots = {}
    with open(JEVNOTES_SHEET2_CSV, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lots[row["LTLOTNBR"].strip()] = {
                "slr_cd": row["LTSLRNBR"].strip(),
                "stage": row["LTLOTSTG"].strip(),
                "status": row["Lot status"].strip(),
            }
    return lots


def _record_time_str(cen, yr, mo, day, rec_time):
    try:
        year = int(cen) * 100 + int(yr)
        month = int(mo)
        d = int(day)
        t = str(int(rec_time)).zfill(6)
        hh, mm, ss = t[0:2], t[2:4], t[4:6]
        return f"{year:04d}-{month:02d}-{d:02d} {hh}:{mm}:{ss}"
    except (ValueError, TypeError):
        return ""


def load_lot_notes():
    """Returns {lot_number: [(sort_key, formatted_line), ...]} sorted chronologically."""
    lots = {}
    with open(JEVNOTES_SHEET1_CSV, encoding="latin-1") as f:
        reader = csv.DictReader(f)
        # header cells contain internal whitespace runs, e.g. 'App                 Cde'
        fieldmap = {name.split()[0] + "".join(w.capitalize() for w in name.split()[1:]): name for name in reader.fieldnames}
        lot_col = fieldmap.get("AppCde") or "App                 Cde"
        seq_col = fieldmap.get("SeqNbr") or "Seq                 Nbr"
        code_col = fieldmap.get("AutoNoteCode") or "Auto                Note                Code"
        text_col = "Note Text"
        cen_col = fieldmap.get("RcdCen") or "Rcd                 Cen"
        yr_col = fieldmap.get("RcdYr") or "Rcd                 Yr"
        mo_col = fieldmap.get("RcdMo") or "Rcd                 Mo"
        day_col = fieldmap.get("RcdDay") or "Rcd                 Day"
        time_col = "Record              Time"

        for row in reader:
            lot = row[lot_col].strip()
            ts = _record_time_str(row[cen_col], row[yr_col], row[mo_col], row[day_col], row[time_col])
            code = row[code_col].strip()
            text = row[text_col].strip()
            seq = row[seq_col].strip()
            line = f"{ts}  {code}  {text}".strip() if ts else f"{code}  {text}".strip()
            sort_key = (ts, int(seq) if seq.isdigit() else 0)
            lots.setdefault(lot, []).append((sort_key, line))
    for lot in lots:
        lots[lot].sort(key=lambda pair: pair[0])
    return lots


def format_instructions_text(seller):
    lines = []
    for key in FIELD_ORDER:
        value = seller["fields"].get(key)
        if value:
            lines.append(f"{NOTE_FIELD_LABELS[key]}: {value}")
    return "\n".join(lines)


def format_notes_text(note_lines):
    return "\n".join(line for _sort_key, line in note_lines)


def build():
    instructions = load_instructions()
    lot_seller_map = load_lot_seller_map()
    lot_notes = load_lot_notes()

    dataset = {}
    skipped_no_instructions = 0
    skipped_no_notes = 0

    # raw source counts, captured before any filtering, for the stats page
    raw_note_line_count = sum(len(lines) for lines in lot_notes.values())
    raw_mapping_row_count = len(lot_seller_map)
    raw_instruction_field_count = sum(len(s["fields"]) for s in instructions.values())

    for lot, meta in lot_seller_map.items():
        slr_cd = meta["slr_cd"]
        seller = instructions.get(slr_cd)
        if not seller:
            skipped_no_instructions += 1
            continue
        notes = lot_notes.get(lot)
        if not notes:
            skipped_no_notes += 1
            continue

        seller_entry = dataset.setdefault(
            slr_cd,
            {
                "slr_comp_cd": seller["slr_comp_cd"],
                "slr_nm": seller["slr_nm"],
                "instructions_text": format_instructions_text(seller),
                "lots": {},
            },
        )
        seller_entry["lots"][lot] = {
            "stage": meta["stage"],
            "status": meta["status"],
            "notes_text": format_notes_text(notes),
            "note_count": len(notes),
        }

    with open(OUT_PATH, "w") as f:
        json.dump(dataset, f, indent=2)

    total_lots = sum(len(v["lots"]) for v in dataset.values())

    stage_counts = {}
    status_counts = {}
    lots_per_seller = {}
    for slr_cd, seller_entry in dataset.items():
        lots_per_seller[slr_cd] = {
            "slr_comp_cd": seller_entry["slr_comp_cd"],
            "slr_nm": seller_entry["slr_nm"],
            "lot_count": len(seller_entry["lots"]),
        }
        for lot_meta in seller_entry["lots"].values():
            stage_counts[lot_meta["stage"]] = stage_counts.get(lot_meta["stage"], 0) + 1
            status_counts[lot_meta["status"]] = status_counts.get(lot_meta["status"], 0) + 1

    stats = {
        "seller_code_count": len(dataset),
        "total_lots": total_lots,
        "lots_per_seller": lots_per_seller,
        "stage_counts": stage_counts,
        "status_counts": status_counts,
        "source_row_counts": {
            "instructions_csv_field_rows": raw_instruction_field_count,
            "lot_seller_mapping_rows": raw_mapping_row_count,
            "raw_note_line_rows": raw_note_line_count,
        },
        "skipped_no_instructions": skipped_no_instructions,
        "skipped_no_notes": skipped_no_notes,
    }
    with open(STATS_OUT_PATH, "w") as f:
        json.dump(stats, f, indent=2)

    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {STATS_OUT_PATH}")
    print(f"Seller codes: {len(dataset)}, lots: {total_lots}")
    print(f"Skipped (no instructions for seller code): {skipped_no_instructions}")
    print(f"Skipped (no note history found): {skipped_no_notes}")


if __name__ == "__main__":
    build()
