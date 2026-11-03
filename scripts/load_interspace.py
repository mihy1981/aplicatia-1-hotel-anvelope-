#!/usr/bin/env python3
"""Încarcă anunțurile Interspace (JSON extras din emailuri) în tab-ul 'Anunturi_Curier'.

Un email Interspace = un ANUNȚ de expediere prin curier (NU dovada sosirii). SOSIRE -> ANUNTAT (până la
recepție), PLECARE -> DE_PREDAT (până la predarea la curier). Anulările se sar. Deduplicare după AWB.

    python scripts/load_interspace.py interspace.json --dry-run
    python scripts/load_interspace.py interspace.json

Scrie DOAR în 'Anunturi_Curier' (niciodată în 'Inventar GY'). Emailurile nu sunt atinse.
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import receptii_import as rimp  # noqa: E402
from import_receptie import DEFAULT_SHEET, NOT, ensure_ws, open_sheet, ws_records  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Anunțuri Interspace -> Anunturi_Curier")
    ap.add_argument("file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sheet", default=os.environ.get("MADYT_SPREADSHEET_ID", DEFAULT_SHEET))
    a = ap.parse_args(argv)
    with open(a.file, encoding="utf-8") as f:
        items = json.load(f)
    sh = open_sheet(a.sheet)
    existing = [r.get("AWB", "") for r in ws_records(sh, NOT)]
    rows, skipped = rimp.notices_from_interspace(items, existing, created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    for r in rows:
        r["Operator"] = "load_interspace.py"
        print(f"{r['Direction']:8} {r['Status']:11} {r['NoticeDate'][:10]} AWB {r['AWB']} "
              f"{r['RegistrationNumber'] or r['VIN']:18} {r['ExpectedTyres']} anv. {r['Counterparty']}")
    print(f"{len(rows)} anunțuri noi (sosiri: {sum(r['Direction'] == rimp.N_IN for r in rows)}, "
          f"plecări: {sum(r['Direction'] == rimp.N_OUT for r in rows)}); anulate/sărite: {len(skipped)}; "
          f"deja în foaie: {len([x for x in existing if x])}")
    if a.dry_run or not rows:
        print("[dry-run] nimic scris." if a.dry_run else "Nimic de scris.")
        return 0
    ws, head = ensure_ws(sh, NOT, rimp.NOT_COLS)
    ws.append_rows([[r.get(c, "") for c in head] for r in rows], value_input_option="RAW")
    print(f"✅ {len(rows)} anunțuri scrise în {NOT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
