#!/usr/bin/env python3
"""Import recepții leasing din Excel/CSV (un rând = o anvelopă, coloane tip GY) în Google Sheet.

Utilizare:
    python scripts/import_receptie.py fisier.xlsx --dry-run
    python scripts/import_receptie.py fisier.xlsx --fleet HERTZ --date 2026-11-03 [--condition FOLOSITE]

Credențiale: MADYT_SA_FILE (implicit /workspace/.secrets/sa.json). Sheet: --sheet / MADYT_SPREADSHEET_ID.
Scrie DOAR în tab-urile Receptii, Receptii_Anvelope, Istoric (niciodată în 'Inventar GY').
"""
import argparse
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import receptii_import as rimp  # noqa: E402

DEFAULT_SHEET = "1qs5DuQ4--vT0Tr91sqH2om4B1dHM_-IyNLnkcvL5leA"
REC, RTY, IST, HOTEL = "Receptii", "Receptii_Anvelope", "Istoric", "Hotel"
IST_COLS = ["Timestamp", "RegistrationNumber", "Action", "Details", "PositionCode", "UserNote", "Operator"]
ALLOWED = {REC: rimp.REC_COLS, RTY: rimp.RTY_COLS, IST: IST_COLS}


def open_sheet(sheet_id):
    import gspread
    sa = os.environ.get("MADYT_SA_FILE", "/workspace/.secrets/sa.json")
    return gspread.service_account(filename=sa).open_by_key(sheet_id)


def ws_records(sh, name):
    try:
        vals = sh.worksheet(name).get_all_values()
    except Exception:  # tab inexistent
        return []
    if not vals:
        return []
    h = vals[0]
    return [dict(zip(h, r + [""] * (len(h) - len(r)))) for r in vals[1:]]


def ensure_ws(sh, name, cols):
    """Creează tab-ul dacă lipsește; adaugă la final coloanele lipsă. Întoarce (ws, header)."""
    assert name in ALLOWED, name
    import gspread
    try:
        ws = sh.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(name, rows=1000, cols=max(26, len(cols)))
    head = ws.row_values(1)
    miss = [c for c in cols if c not in head]
    if miss:
        new = head + miss
        if len(new) > ws.col_count:
            ws.add_cols(len(new) - ws.col_count)
        ws.update(range_name="A1", values=[new])
        head = new
    return ws, head


def append(sh, name, rows):
    if not rows:
        return
    ws, head = ensure_ws(sh, name, ALLOWED[name])
    ws.append_rows([[r.get(c, "") for c in head] for r in rows], value_input_option="RAW")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Import recepții leasing (Excel/CSV)")
    ap.add_argument("file")
    ap.add_argument("--dry-run", action="store_true", help="doar afișează planul, nu scrie nimic")
    ap.add_argument("--sheet", default=os.environ.get("MADYT_SPREADSHEET_ID", DEFAULT_SHEET))
    ap.add_argument("--fleet", default="", help="flota implicită dacă fișierul nu are coloană")
    ap.add_argument("--date", default=date.today().isoformat(), help="data recepției (YYYY-MM-DD)")
    ap.add_argument("--condition", default="NOI", choices=rimp.CONDITIONS)
    ap.add_argument("--location", default="", help="locație de așteptare")
    ap.add_argument("--allow-duplicates", action="store_true", help="importă și mașinile cu recepție deschisă")
    ap.add_argument("--offline", action="store_true", help="dry-run fără a citi Google Sheet")
    a = ap.parse_args(argv)

    with open(a.file, "rb") as f:
        raw = rimp.read_file(a.file, f.read())
    mapping = rimp.auto_map(raw.columns)
    print("Coloane mapate:", ", ".join(f"{rimp.LABELS_RO.get(k, k)} ← {v}" for k, v in mapping.items()))
    miss = rimp.missing_required(mapping)
    if miss:
        print("EROARE: lipsesc coloanele obligatorii:", ", ".join(miss))
        return 2

    sh, open_pl, open_vin, vin2plate = None, set(), set(), {}
    if not a.offline:
        sh = open_sheet(a.sheet)
        for r in ws_records(sh, REC):
            if r.get("Status", "").strip().upper() == "RECEPTIONAT":
                open_pl.add(rimp.norm_plate(r.get("RegistrationNumber", "")))
                open_vin.add(rimp.norm_vin(r.get("VIN", "")))
        for r in ws_records(sh, HOTEL):
            v = rimp.norm_vin(r.get("VIN", ""))
            if v:
                vin2plate[v] = rimp.norm_plate(r.get("RegistrationNumber", ""))
    recs, warns, skipped = rimp.build_plan(raw, mapping, open_pl, a.fleet, open_vin, a.condition)
    for r in recs:
        if not r["RegistrationNumber"] and r["VIN"] in vin2plate:
            r["RegistrationNumber"] = vin2plate[r["VIN"]]
    for line in rimp.plan_table(recs).to_string(index=False).splitlines():
        print(line)
    for w in warns:
        print("⚠️ ", w)
    if skipped:
        print(f"{skipped} rânduri ignorate (fără număr/VIN sau totaluri)")
    if a.dry_run or a.offline:
        print(f"[dry-run] {len(recs)} recepții ar fi create. Nimic scris.")
        return 0

    now = datetime.now()
    rec_rows, rty_rows, ist_rows, done = [], [], [], []
    for k, r in enumerate(recs):
        plate, vin = r["RegistrationNumber"], r["VIN"]
        tyres = [t for t in r["tyres"] if t["MaterialDescription"]]
        if not tyres or (not a.allow_duplicates and ((plate and plate in open_pl) or (vin and vin in open_vin))):
            print("sărit:", plate or vin)
            continue
        rid = f"RC{now.strftime('%Y%m%d%H%M%S')}{k:03d}-{plate or vin[-6:]}"
        rec_rows.append({"ReceptionId": rid, "RegistrationNumber": plate, "FleetName": r["FleetName"],
                         "ReceptionDate": a.date, "Tyres": str(len(tyres)), "Season": rimp.season_of(tyres),
                         "WaitingLocation": a.location, "Status": "RECEPTIONAT",
                         "CreatedAt": now.strftime("%Y-%m-%d %H:%M:%S"), "Operator": "import_receptie.py",
                         "UserName": r["UserName"], "UserPhone": r["UserPhone"], "ClientCompany": r["ClientCompany"],
                         "VIN": vin, "Condition": r["Condition"]})
        for n, t in enumerate(tyres, 1):
            rty_rows.append({**t, "ReceptionId": rid, "TyreNo": str(n), "RegistrationNumber": plate})
        ist_rows.append({"Timestamp": now.strftime("%Y-%m-%d %H:%M:%S"), "RegistrationNumber": plate or f"VIN {vin}",
                         "Action": "RECEPTIE_LEASING", "Operator": "import_receptie.py",
                         "Details": f"Recepție leasing {rid} (import: {os.path.basename(a.file)}), "
                                    f"{r['Condition']}, {len(tyres)} anv."})
        done.append(plate or vin)
    append(sh, RTY, rty_rows)
    append(sh, REC, rec_rows)
    append(sh, IST, ist_rows)
    print(f"✅ {len(done)} recepții create: {', '.join(done)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
