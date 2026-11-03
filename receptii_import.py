# -*- coding: utf-8 -*-
"""Import în masă al recepțiilor de leasing (Excel/CSV, un rând pe anvelopă).

Modul fără Streamlit, folosit și de aplicație și de scriptul scripts/import_receptie.py.
Rezultatul: o recepție (status RECEPTIONAT) pe număr auto, cu anvelopele ei.
"""
import io
import re
from collections import Counter

import pandas as pd

REC_COLS = ["ReceptionId", "RegistrationNumber", "FleetName", "ReceptionDate", "Tyres", "Season", "WaitingLocation",
            "Note", "Status", "SwapDate", "MyWayDate", "CreatedAt", "Operator", "UserName", "UserPhone", "ClientCompany",
            "VIN", "Condition"]
RTY_COLS = ["ReceptionId", "TyreNo", "RegistrationNumber", "MaterialDescription", "BRAND", "TyreModel",
            "ProductGroup", "DOT", "TreadDepth", "Axle", "Note"]
CONDITIONS = ["NOI", "FOLOSITE"]

# câmp intern -> nume de coloane posibile (comparate fără spații/diacritice/majuscule)
FIELDS = {
    "RegistrationNumber": ["RegistrationNumber", "Nr auto", "Numar auto", "Număr auto", "Nr. inmatriculare", "Plate",
                           "Inmatriculare", "Nr inmatriculare", "Registration"],
    "VIN": ["VIN", "Chassis Num", "Chassis Number", "Serie sasiu", "Serie șasiu", "Sasiu", "Șasiu", "Fleet VIN",
            "Nr. sasiu", "Chassis"],
    "Condition": ["Condition", "Stare", "Tip", "Noi/Folosite", "Stare anvelope"],
    "FleetName": ["FleetName", "Flota", "Flotă", "Fleet", "Leasing"],
    "MaterialDescription": ["MaterialDescription", "Dimensiune", "Descriere", "Anvelopa", "Anvelopă", "Size",
                            "Description", "Material Description"],
    "BRAND": ["BRAND", "Marca", "Marcă", "Brand", "Producator"],
    "TyreModel": ["TyreModel", "Model anvelopa", "Model anvelopă", "Model", "Pattern", "Profil model"],
    "ProductGroup": ["ProductGroup", "Sezon", "Season", "Product Group"],
    "DOT": ["DOT"],
    "TreadDepth": ["TreadDepth", "Profil (mm)", "Profil", "mm", "Uzura", "Uzură", "Uzura mm", "Tread", "Adancime"],
    "Axle": ["Axle", "Pozitie", "Poziție", "Pozitie pe masina", "Ax", "ServiceProviderStorageLocation"],
    "Note": ["Note", "Observatii", "Observații", "Nota", "Notă", "StorageNote(Comments/AccessoriesStored)", "Comments"],
    "QUANTITY": ["QUANTITY", "Cantitate", "Qty", "Buc"],
    "UserName": ["UserName", "Utilizator", "User", "Sofer", "Șofer", "Driver", "Nume utilizator"],
    "UserPhone": ["UserPhone", "Telefon utilizator", "Telefon", "Phone", "Tel"],
    "ClientCompany": ["ClientCompany", "Firma client", "Firmă client", "Client", "Companie", "Company", "Beneficiar"],
}
REQUIRED = ["MaterialDescription"]  # + număr auto SAU VIN
LABELS_RO = {
    "RegistrationNumber": "Număr auto (sau VIN)", "VIN": "VIN / serie șasiu (sau număr auto)",
    "Condition": "Stare (NOI / FOLOSITE)", "FleetName": "Flotă", "MaterialDescription": "Dimensiune / descriere *",
    "BRAND": "Marcă", "TyreModel": "Model anvelopă", "ProductGroup": "Sezon", "DOT": "DOT", "TreadDepth": "Profil (mm)",
    "Axle": "Poziție pe mașină", "Note": "Observații", "QUANTITY": "Cantitate (rânduri cu >1 se multiplică)",
    "UserName": "Utilizator", "UserPhone": "Telefon utilizator", "ClientCompany": "Firmă client",
}
AXLE_GY = {"DF": "FD", "SF": "FS", "DS": "SD", "SS": "SS", "FD": "FD", "FS": "FS", "SD": "SD"}


def _k(s):
    s = str(s).lower()
    for a, b in (("ă", "a"), ("â", "a"), ("î", "i"), ("ș", "s"), ("ş", "s"), ("ț", "t"), ("ţ", "t")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def norm_plate(p):
    return re.sub(r"[^A-Z0-9]", "", str(p).upper())


def norm_vin(v):
    v = re.sub(r"[^A-Z0-9]", "", str(v).upper())
    return v if len(v) >= 6 else ""


def norm_condition(c, default="NOI"):
    k = _k(c)
    if k.startswith("fol") or k in ("used", "uzate", "second", "sh"):
        return "FOLOSITE"
    if k.startswith("no") or k == "new":
        return "NOI"
    return default


def norm_season(s):
    k = _k(s)
    if k in ("winter", "iarna", "w"):
        return "Winter"
    if k in ("summer", "vara", "s"):
        return "Summer"
    if k.startswith("all") or "4season" in k or k in ("allseason", "allseasons"):
        return "All Season"
    return str(s).strip()


def read_file(name, data):
    """Fișier (nume, bytes) -> DataFrame text. La Excel cu mai multe foi se ia prima foaie cu date."""
    if str(name).lower().endswith(".csv"):
        raw = data.decode("utf-8-sig", errors="replace")
        sep = ";" if raw.count(";") > raw.count(",") else ","
        df = pd.read_csv(io.StringIO(raw), dtype=str, sep=sep, keep_default_na=False)
    else:
        sheets = pd.read_excel(io.BytesIO(data), dtype=str, sheet_name=None)
        df = next((d for d in sheets.values() if len(d)), pd.DataFrame())
    df = df.fillna("").astype(str)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if not c.lower().startswith("unnamed")] or list(df.columns)]
    return df[df.apply(lambda r: any(str(x).strip() for x in r), axis=1)].reset_index(drop=True)


def auto_map(columns):
    """Potrivește automat coloanele fișierului pe câmpurile interne. Întoarce {câmp: coloană}."""
    keyed = {}
    for c in columns:
        keyed.setdefault(_k(c), c)
    out, used = {}, set()
    for f, aliases in FIELDS.items():
        for a in aliases:
            c = keyed.get(_k(a))
            if c is not None and c not in used:
                out[f] = c
                used.add(c)
                break
    return out


def _fmt_mm(s):
    s = str(s).strip()
    m = re.findall(r"\d+(?:[.,]\d+)?", s)
    vals = [float(x.replace(",", ".")) for x in m if float(x.replace(",", ".")) < 30]
    return f"{min(vals):.1f}".replace(".", ",") if vals else s


def build_plan(df, mapping, open_plates=(), default_fleet="", open_vins=(), default_condition="NOI"):
    """Grupează pe număr auto. Întoarce (recepții, avertismente, rânduri_ignorate).

    recepție = {"RegistrationNumber", "FleetName", "UserName", "UserPhone", "ClientCompany", "tyres": [...],
                "warnings": [...]}
    """
    def g(r, f):
        c = mapping.get(f)
        return str(r.get(c, "")).strip() if c else ""

    open_plates = {norm_plate(p) for p in open_plates if norm_plate(p)}
    open_vins = {norm_vin(v) for v in open_vins if norm_vin(v)}
    groups, skipped, warnings = {}, 0, []
    for i, r in df.iterrows():
        plate = norm_plate(g(r, "RegistrationNumber"))
        vin = norm_vin(g(r, "VIN"))
        desc = g(r, "MaterialDescription").upper()
        if not plate and not vin:
            if any(str(x).strip() for x in r.values):
                skipped += 1
            continue
        if plate and re.search(r"total|count", plate, re.I):
            skipped += 1
            continue
        q = g(r, "QUANTITY")
        try:
            n = max(1, min(8, int(float(q.replace(",", "."))))) if q else 1
        except ValueError:
            n = 1
        key = plate or f"VIN:{vin}"
        rec = groups.setdefault(key, {"RegistrationNumber": plate, "VIN": vin, "FleetName": "", "UserName": "",
                                      "UserPhone": "", "ClientCompany": "", "Condition": "", "tyres": [],
                                      "warnings": []})
        if vin and not rec["VIN"]:
            rec["VIN"] = vin
        if not rec["Condition"] and g(r, "Condition"):
            rec["Condition"] = norm_condition(g(r, "Condition"), default_condition)
        for f in ("FleetName", "UserName", "UserPhone", "ClientCompany"):
            if not rec[f] and g(r, f):
                rec[f] = g(r, f)
        axle = g(r, "Axle").upper()
        axle = AXLE_GY.get(axle, axle if axle in ("FS", "FD", "SS", "SD") else "")
        for _ in range(n):
            rec["tyres"].append({
                "MaterialDescription": desc, "BRAND": g(r, "BRAND").upper(), "TyreModel": g(r, "TyreModel").upper(),
                "ProductGroup": norm_season(g(r, "ProductGroup")), "DOT": g(r, "DOT"),
                "TreadDepth": _fmt_mm(g(r, "TreadDepth")), "Axle": axle, "Note": g(r, "Note"),
            })
        if not desc:
            rec["warnings"].append(f"rândul {i + 2}: lipsește dimensiunea")
    for key, rec in groups.items():
        rec["FleetName"] = rec["FleetName"] or default_fleet
        rec["Condition"] = rec["Condition"] or default_condition
        if (rec["RegistrationNumber"] and rec["RegistrationNumber"] in open_plates) or (rec["VIN"] and rec["VIN"] in open_vins):
            rec["warnings"].append("are deja o recepție deschisă (RECEPTIONAT)")
        if not rec["RegistrationNumber"]:
            rec["warnings"].append("doar VIN, fără număr auto (se leagă de mașină ulterior)")
        if len(rec["tyres"]) != 4:
            rec["warnings"].append(f"{len(rec['tyres'])} anvelope (nu 4)")
        seasons = {t["ProductGroup"] for t in rec["tyres"] if t["ProductGroup"]}
        if len(seasons) > 1:
            rec["warnings"].append("sezoane amestecate")
        if not rec["FleetName"]:
            rec["warnings"].append("fără flotă")
        if rec["warnings"]:
            warnings.append(f"{rec['RegistrationNumber'] or 'VIN ' + rec['VIN']}: " + "; ".join(rec["warnings"]))
    missing = [LABELS_RO[f] for f in REQUIRED if f not in mapping]
    if "RegistrationNumber" not in mapping and "VIN" not in mapping:
        missing.append("Număr auto sau VIN")
    if missing:
        warnings.insert(0, "Coloane obligatorii nemapate: " + ", ".join(missing))
    return list(groups.values()), warnings, skipped


def missing_required(mapping):
    m = [f for f in REQUIRED if f not in mapping]
    if "RegistrationNumber" not in mapping and "VIN" not in mapping:
        m.append("RegistrationNumber/VIN")
    return m


def plan_table(recs):
    """Tabel de previzualizare: un rând pe număr auto."""
    rows = []
    for r in recs:
        rows.append({
            "Număr auto": r["RegistrationNumber"], "VIN": r["VIN"], "Stare": r["Condition"], "Flotă": r["FleetName"], "Utilizator": r["UserName"],
            "Firmă client": r["ClientCompany"], "Nr. anv.": len(r["tyres"]),
            "Dimensiuni": " | ".join(sorted({t["MaterialDescription"] for t in r["tyres"]})),
            "Sezon": "/".join(sorted({t["ProductGroup"] for t in r["tyres"] if t["ProductGroup"]})),
            "Avertismente": "; ".join(r["warnings"]),
        })
    return pd.DataFrame(rows)


def season_of(tyres):
    c = Counter(t.get("ProductGroup", "") for t in tyres if t.get("ProductGroup", ""))
    return "/".join(k for k, _ in c.most_common())
