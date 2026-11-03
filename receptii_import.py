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
            "VIN", "Condition", "AWB", "NoticeId"]
RTY_COLS = ["ReceptionId", "TyreNo", "RegistrationNumber", "MaterialDescription", "BRAND", "TyreModel",
            "ProductGroup", "DOT", "TreadDepth", "Axle", "Note", "MaterialCode"]
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
    "MaterialCode": ["MaterialCode", "Cod material", "MaterialNumber", "Material Number", "Cod GY", "Cod articol",
                     "Material"],
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
    "MaterialCode": "Cod material GY",
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
        sheets = pd.read_excel(io.BytesIO(data), dtype=str, sheet_name=None, header=None)
        df = next((d for d in sheets.values() if len(d.dropna(how="all"))), pd.DataFrame())
        df = df.dropna(how="all").reset_index(drop=True)
        hl = headerless_columns(df)
        if hl:
            df.columns = hl
        elif len(df):
            names, seen = [], {}
            for k, c in enumerate(df.iloc[0]):
                c = ("" if pd.isna(c) else str(c).strip()) or f"Unnamed: {k}"
                seen[c] = seen.get(c, -1) + 1
                names.append(c if not seen[c] else f"{c}.{seen[c]}")
            df.columns = names
            df = df.iloc[1:]
    df = df.fillna("").astype(str).apply(lambda col: col.str.replace("\xa0", " ").str.strip())
    df.columns = [str(c).strip() for c in df.columns]
    df = df.loc[:, [c for c in df.columns if not c.lower().startswith("unnamed")] or list(df.columns)]
    return df[df.apply(lambda r: any(str(x).strip() for x in r), axis=1)].reset_index(drop=True)


SIZE_RE = re.compile(r"\b(\d{3})\s*/\s*(\d{2})\s*Z?R\s*(\d{2}(?:[.,]5)?)\s*(C)?\b", re.I)
SIZE_RE_ALT = re.compile(r"\b(\d{3})\s*R\s*(\d{2})\s*(C)?\b", re.I)
LI_RE = re.compile(r"^\s*(\d{2,3}(?:/\d{2,3})?\s*[A-Z])\b(?:\s+(?:XL|RF|C))*", re.I)
PLATE_RE = re.compile(r"^[A-Z]{1,2}\s*\d{2,6}\s*[A-Z]{0,3}$")
# prescurtări din descrierile GY -> marcă (ordinea contează: cheile mai lungi primele)
BRANDS = [("UG PERF", "GOODYEAR"), ("ULTRAGRIP", "GOODYEAR"), ("EFFICIENTGRIP", "GOODYEAR"), ("EAGLE", "GOODYEAR"),
          ("VECTOR", "GOODYEAR"), ("CARGO", "GOODYEAR"), ("ESKIMO", "SAVA"), ("INTENSA", "SAVA"),
          ("FRIGO", "DEBICA"), ("PRESTO", "DEBICA"), ("KRI CONTROL", "FULDA"), ("KRISTALL", "FULDA"), ("WINTER SPT", "DUNLOP"), ("SP WINTER", "DUNLOP")]
KNOWN_BRANDS = ["GOODYEAR", "COOPER", "KUMHO", "DUNLOP", "SAVA", "DEBICA", "FULDA", "MICHELIN", "BRIDGESTONE",
                "CONTINENTAL", "HANKOOK", "PIRELLI", "NOKIAN", "BARUM", "FIRESTONE", "KLEBER", "KORMORAN", "TIGAR",
                "RIKEN", "BFGOODRICH", "UNIROYAL", "SEMPERIT", "GENERAL", "VREDESTEIN", "NEXEN", "TOYO", "YOKOHAMA",
                "FALKEN", "LASSA", "MATADOR", "LAUFENN", "MAXXIS", "NANKANG", "GISLAVED", "PETLAS"]
WINTER_KW = ["WINTER", "WIN ", "WIN VAN", "ULTRAGRIP", "UG PERF", "UG 9", "ESKIMO", "FRIGO", "SNOW", "ALPIN",
             "KRISALP", "WS71", "CW51", "WP52", "WP51", "WS31", "POLARIS", "SNOVANIS", "NORDIC", "ICE",
             "WINTERCRAFT", "BLIZZAK", "KRI CONTROL", " ICE "]
SUMMER_KW = ["SUMMER", "EFFICIENTGRIP", "EAGLE F1", "PRIMACY", "PILOT SPORT", "INTENSA", "PRESTO", "ECSTA", "VENTUS",
             "TURANZA", "PREMIUMCONTACT", "ECOCONTACT", "SPORTCONTACT", "VANCONT", "D684"]
ALLSEASON_KW = ["4SEASON", "ALL SEASON", "ALLSEASON", "VECTOR", "CROSSCLIMATE", "QUATRAC", "4S ", "ALL WEATHER"]


def parse_desc(desc):
    """Descriere GY (ex. '225/60R17 103V COOPER WINTER XL') -> {MaterialDescription (fără marcă), BRAND, TyreModel,
    ProductGroup}. Ce nu se poate deduce rămâne gol (editabil în aplicație)."""
    d = re.sub(r"\s+", " ", str(desc).upper().replace("\xa0", " ")).strip()
    if not d:
        return {"MaterialDescription": "", "BRAND": "", "TyreModel": "", "ProductGroup": ""}
    m = SIZE_RE.search(d) or SIZE_RE_ALT.search(d)
    brand = next((b for b in KNOWN_BRANDS if re.search(rf"\b{b}\b", d)), "")
    if not brand:
        brand = next((b for k, b in BRANDS if k in d), "")
    rest = d
    size = ""
    if m:
        size = re.sub(r"\s+", "", m.group(0))
        rest = (d[:m.start()] + " " + d[m.end():]).strip()
        li = re.match(r"^\s*(\d{2,3}(?:/\d{2,3})?\s*[A-Z])\b", rest)
        if li and not re.match(r"^\s*\d{2,3}(?:/\d{2,3})?\s*[A-Z]{2,}", rest):
            size += " " + re.sub(r"\s+", "", li.group(1))
            rest = rest[li.end():].strip()
    if brand:
        rest = re.sub(rf"\b{brand}\b", " ", rest).strip()
    rest = re.sub(r"\s+", " ", rest).strip()
    # indice de sarcină poziționat după marcă (ex. 'KUMHO 113R CW51')
    if m and " " not in size:
        li = re.match(r"^(\d{2,3}(?:/\d{2,3})?[A-Z])\b\s*", rest)
        if li:
            size += " " + li.group(1)
            rest = rest[li.end():].strip()
    model = rest
    p = f" {d} "
    season = ""
    if any(k in p for k in ALLSEASON_KW):
        season = "All Season"
    elif any(k in p for k in WINTER_KW):
        season = "Winter"
    elif any(k in p for k in SUMMER_KW):
        season = "Summer"
    md = (size + (" " + model if model else "")).strip() if size else d
    return {"MaterialDescription": md, "BRAND": brand, "TyreModel": model, "ProductGroup": season}


def headerless_columns(df):
    """Fișier fără antet (ex. livrare GY: A nr. auto, B punct livrare, C cod material, D descriere, E cantitate).
    Întoarce numele coloanelor sau None dacă primul rând arată a antet."""
    if df is None or not len(df) or len(df.columns) < 2:
        return None
    sample = df.head(40).fillna("").astype(str).apply(lambda c: c.str.replace("\xa0", " ").str.strip())
    first = [str(x) for x in sample.iloc[0]]
    if len(auto_map(first)) >= 2:
        return None  # are antet recunoscut
    def share(col, pred):
        vals = [v for v in sample[col] if v]
        return (sum(1 for v in vals if pred(v)) / len(vals)) if vals else 0
    cols = list(df.columns)
    plate_c = next((c for c in cols if share(c, lambda v: bool(PLATE_RE.match(v.upper())) or bool(norm_vin(v)) and len(v) == 17) >= 0.8), None)
    desc_c = next((c for c in cols if share(c, lambda v: bool(SIZE_RE.search(v.upper()) or SIZE_RE_ALT.search(v.upper()))) >= 0.8), None)
    if plate_c is None or desc_c is None:
        return None
    names = {plate_c: "RegistrationNumber", desc_c: "MaterialDescription"}
    rest = [c for c in cols if c not in names]
    qty_c = next((c for c in reversed(rest) if share(c, lambda v: v.isdigit() and int(v) <= 12) >= 0.8), None)
    if qty_c is not None:
        names[qty_c] = "QUANTITY"
    code_c = next((c for c in rest if c not in names and share(c, lambda v: v.isdigit() and len(v) >= 5) >= 0.6), None)
    if code_c is not None:
        names[code_c] = "MaterialCode"
    k = 0
    out = []
    for c in cols:
        if c in names:
            out.append(names[c])
        else:
            k += 1
            out.append("Punct livrare" if k == 1 else f"Coloana {k}")
    return out


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
            n = max(1, min(12, int(float(q.replace(",", "."))))) if q else 1
        except ValueError:
            n = 1
        pd_ = parse_desc(desc)
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
            brand = g(r, "BRAND").upper()
            rec["tyres"].append({
                # fără coloană de marcă: dimensiunea / marca / modelul / sezonul se deduc din descriere
                "MaterialDescription": desc if brand else pd_["MaterialDescription"],
                "BRAND": brand or pd_["BRAND"], "TyreModel": g(r, "TyreModel").upper() or ("" if brand else pd_["TyreModel"]),
                "ProductGroup": norm_season(g(r, "ProductGroup")) or pd_["ProductGroup"], "DOT": g(r, "DOT"),
                "TreadDepth": _fmt_mm(g(r, "TreadDepth")), "Axle": axle, "Note": g(r, "Note"),
                "MaterialCode": g(r, "MaterialCode"),
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
        if len(rec["tyres"]) not in (4, 6):
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
            "Mărci": " | ".join(sorted({t["BRAND"] for t in r["tyres"] if t["BRAND"]})),
            "Dimensiuni": " | ".join(sorted({t["MaterialDescription"] for t in r["tyres"]})),
            "Sezon": "/".join(sorted({t["ProductGroup"] for t in r["tyres"] if t["ProductGroup"]})),
            "Avertismente": "; ".join(r["warnings"]),
        })
    return pd.DataFrame(rows)


def season_of(tyres):
    c = Counter(t.get("ProductGroup", "") for t in tyres if t.get("ProductGroup", ""))
    return "/".join(k for k, _ in c.most_common())


# ---------------------------------------------------------------------------
# Completare din evidențe (Hotel, Hotel_Anvelope, Inventar GY, inventare vechi) – doar citire
# ---------------------------------------------------------------------------
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")
_JUNK_FLEET = re.compile(r"total|count|acum|avem|anv\b|pe care|\d", re.I)


def _plates_in(s):
    """'AG061763/B161AJB', 'B113AJB Count' -> ['AG061763', 'B161AJB'] / ['B113AJB']."""
    s = re.sub(r"\bCOUNT\b", " ", str(s).upper())
    out = []
    for tok in re.split(r"[/,;|]+", s):
        p = norm_plate(tok)
        if 4 <= len(p) <= 10 and re.match(r"^[A-Z]{1,2}\d", p):
            out.append(p)
    return out


def ref_index(frames):
    """frames: [(nume_sursă, DataFrame)] -> {plate: {"sources": [...], "FleetName", "VIN", "UserName", "ClientCompany",
    "Make/Model", "sizes": set(), "status": str}} (prima sursă are prioritate). Tolerează rânduri decalate."""
    idx = {}
    for name, df in frames:
        if df is None or not len(df):
            continue
        d = df.fillna("").astype(str)
        fleets_ok = set()
        if "FleetName" in d:
            vc = d["FleetName"].str.strip().value_counts()
            fleets_ok = {f for f, n in vc.items() if f and n >= 2 and not _JUNK_FLEET.search(f)}
        for _, r in d.iterrows():
            vals = [str(v).strip() for v in r.values]
            plates = _plates_in(r.get("RegistrationNumber", ""))
            if not plates:  # rânduri decalate (ex. numărul în coloana 'wms')
                for c in ("wms", "Nr auto"):
                    if c in r and _plates_in(r[c]):
                        plates = _plates_in(r[c])
                        break
            if not plates:
                continue
            vin = ""
            for c in ("VIN", "Chassis Num", "Fleet VIN"):
                v = norm_vin(r.get(c, ""))
                if VIN_RE.match(v):
                    vin = v
                    break
            if not vin:
                vin = next((norm_vin(v) for v in vals if VIN_RE.match(norm_vin(v)) and re.search(r"\d", v) and re.search(r"[A-Z]", v.upper())), "")
            sizes = {re.sub(r"\s+", "", m.group(0)).upper() for v in vals for m in [SIZE_RE.search(v.upper())] if m}
            for p in plates:
                e = idx.setdefault(p, {"sources": [], "FleetName": "", "VIN": "", "UserName": "", "ClientCompany": "",
                                       "Make/Model": "", "sizes": {}, "status": "", "aliases": set()})
                if name not in e["sources"]:
                    e["sources"].append(name)
                e["aliases"].update(set(plates) - {p})
                fl = str(r.get("FleetName", "")).strip()
                if not e["FleetName"] and fl and (fl in fleets_ok or name.lower().startswith("hotel")):
                    e["FleetName"] = fl
                if not e["VIN"] and vin:
                    e["VIN"] = vin
                for k in ("UserName", "ClientCompany"):
                    if not e[k] and str(r.get(k, "")).strip():
                        e[k] = str(r.get(k, "")).strip()
                mm = str(r.get("Make/Model", "")).strip()
                if not e["Make/Model"] and mm and "N/A" not in mm.upper() and not mm.isdigit() and not re.match(r"^\d+\s*BUC", mm.upper()):
                    e["Make/Model"] = mm
                if sizes:
                    e["sizes"].setdefault(name, set()).update(sizes)
                if not e["status"] and str(r.get("Status", "")).strip() and name.lower() == "hotel":
                    e["status"] = str(r.get("Status", "")).strip().upper()
    return idx


def tyre_size(desc):
    m = SIZE_RE.search(str(desc).upper())
    return re.sub(r"\s+", "", m.group(0)).upper() if m else ""


def enrich_plan(recs, idx, notices=()):
    """Completează flota / VIN / utilizator / firmă client din evidențe (doar câmpurile goale) și întoarce
    raportul de comparație: o listă de dicturi pe mașină."""
    report = []
    for r in recs:
        p = r["RegistrationNumber"]
        e = idx.get(p)
        flags, filled = [], []
        if e is None and r.get("VIN"):
            e = next((x for x in idx.values() if x["VIN"] == r["VIN"]), None)
        new_sizes = sorted({tyre_size(t["MaterialDescription"]) for t in r["tyres"]} - {""})
        if e is None:
            flags.append("mașină necunoscută în evidențe")
        else:
            for k in ("FleetName", "VIN", "UserName", "ClientCompany"):
                if not r.get(k) and e.get(k):
                    r[k] = e[k]
                    filled.append(k)
                elif k == "VIN" and r.get(k) and e.get(k) and r[k] != e[k]:
                    flags.append(f"VIN diferit: fișier {r[k]} / evidență {e[k]}")
            stored = sorted(set().union(*e["sizes"].values())) if e["sizes"] else []
            if stored and new_sizes and not set(new_sizes) & set(stored):
                flags.append(f"dimensiune diferită: nou {', '.join(new_sizes)} / evidență {', '.join(stored)}")
            if e["status"] in ("DEPOZITAT", "DECIZIE_GY_ASTEPTATA"):
                flags.append(f"are set în hotel ({e['status']})")
            if e.get("aliases"):
                flags.append("alt nr. în evidență: " + ", ".join(sorted(e["aliases"])))
        ns = [n for n in notices if (norm_plate(n.get("RegistrationNumber", "")) == p and p)
              or (r.get("VIN") and norm_vin(n.get("VIN", "")) == r["VIN"])]
        for n in ns:
            flags.append(f"anunț curier {n.get('Status', '')} AWB {n.get('AWB', '')} din {n.get('NoticeDate', '')}")
        report.append({"Număr auto": p, "VIN": r.get("VIN", ""), "Flotă": r.get("FleetName", ""),
                       "Surse": ", ".join(e["sources"]) if e else "-", "Model": (e or {}).get("Make/Model", ""),
                       "Dim. nouă": ", ".join(new_sizes),
                       "Dim. în evidență": ", ".join(sorted(set().union(*e["sizes"].values()))) if e and e["sizes"] else "",
                       "Completat": ", ".join(filled), "Observații": "; ".join(flags)})
        if r.get("FleetName"):
            r["warnings"] = [w for w in r.get("warnings", []) if w != "fără flotă"]
    return report


# ---------------------------------------------------------------------------
# Anunțuri curier (Interspace / FAN Courier): ANUNTAT (în drum) -> RECEPTIONAT; DE_PREDAT -> PREDAT
# ---------------------------------------------------------------------------
NOT_TAB = "Anunturi_Curier"
NOT_COLS = ["NoticeId", "Direction", "Status", "NoticeDate", "AWB", "Courier", "RegistrationNumber", "VIN",
            "FleetName", "Counterparty", "Contract", "ExpectedTyres", "Season", "Description", "ReceptionId",
            "ClosedDate", "Note", "Source", "CreatedAt", "Operator"]
N_IN, N_OUT = "SOSIRE", "PLECARE"
N_ANN, N_REC, N_CANC, N_DISC = "ANUNTAT", "RECEPTIONAT", "ANULAT", "DISCREPANTA"
N_TODO_OUT, N_DONE_OUT = "DE_PREDAT", "PREDAT"
N_OPEN_IN = (N_ANN, N_DISC)


def notices_from_interspace(items, existing_awbs=(), source="email Interspace", created_at=""):
    """Mesajele Interspace parsate -> rânduri NOT_COLS. Sare peste AWB-urile anulate și cele deja încărcate."""
    cancelled = {str(e.get("awb", "")) for e in items if str(e.get("kind", "")).upper().startswith("ANUL")}
    existing = {str(a) for a in existing_awbs if str(a)}
    out, skipped = [], []
    for e in items:
        kind = str(e.get("kind", "")).upper()
        awb = str(e.get("awb", "")).strip()
        if kind.startswith("ANUL"):
            continue
        if awb in cancelled or awb in existing:
            skipped.append(awb)
            continue
        out_dir = kind.startswith("PLEAC")
        ident = str(e.get("id", "")).strip()
        is_vin = str(e.get("id_type", "")).upper() == "VIN" or bool(VIN_RE.match(norm_vin(ident)))
        desc = e.get("desc") or []
        season = e.get("season") or []
        row = {c: "" for c in NOT_COLS}
        row.update({
            "NoticeId": f"AN-{awb}", "Direction": N_OUT if out_dir else N_IN,
            "Status": N_TODO_OUT if out_dir else N_ANN, "NoticeDate": str(e.get("date", "")),
            "AWB": awb, "Courier": e.get("courier", "") or "FAN Courier",
            "RegistrationNumber": "" if is_vin else norm_plate(ident), "VIN": norm_vin(ident) if is_vin else "",
            "Counterparty": (e.get("to", "") if out_dir else e.get("from", "")) or "",
            "Contract": str(e.get("contract", "") or ""), "ExpectedTyres": str(e.get("qty", "") or ""),
            "Season": "/".join(norm_season(s) for s in season), "Description": " | ".join(desc),
            "Source": f"{source}: {e.get('subject', '')}".strip(), "CreatedAt": created_at,
        })
        out.append(row)
        existing.add(awb)
    return out, skipped


def match_notices(notices, plate="", vin="", awb="", rdate=None):
    """Indicii anunțurilor de SOSIRE deschise potrivite cu o recepție (AWB, număr auto sau VIN). Un anunț trimis
    după data recepției nu se potrivește (setul recepționat e altul)."""
    plate, vin, awb = norm_plate(plate), norm_vin(vin), str(awb or "").strip()
    rd = pd.to_datetime(str(rdate), errors="coerce") if rdate else pd.NaT
    out = []
    for i, n in (notices.iterrows() if hasattr(notices, "iterrows") else enumerate(notices)):
        if n.get("Direction", "") != N_IN or n.get("Status", "") not in N_OPEN_IN:
            continue
        hit = (awb and n.get("AWB", "") == awb) or (plate and norm_plate(n.get("RegistrationNumber", "")) == plate) \
            or (vin and norm_vin(n.get("VIN", "")) == vin)
        if not hit:
            continue
        nd = pd.to_datetime(str(n.get("NoticeDate", ""))[:10], errors="coerce")
        if pd.notna(rd) and pd.notna(nd) and nd.normalize() > rd.normalize() and not (awb and n.get("AWB", "") == awb):
            continue
        out.append(i)
    return out


def notice_tyres(n):
    """Anvelopele așteptate dintr-un anunț (pentru precompletarea recepției)."""
    descs = [d.strip() for d in str(n.get("Description", "")).split("|") if d.strip()]
    try:
        q = int(float(n.get("ExpectedTyres", "") or 0))
    except ValueError:
        q = 0
    seasons = [s for s in str(n.get("Season", "")).split("/") if s]
    if not descs:
        return []
    out = []
    per = [descs[k % len(descs)] for k in range(max(q, len(descs)))]
    for k, d in enumerate(per):
        p = parse_desc(d)
        if not p["ProductGroup"] and seasons:
            p["ProductGroup"] = seasons[min(k, len(seasons) - 1)]
        out.append({**p, "DOT": "", "TreadDepth": "", "Axle": "", "Note": "", "MaterialCode": ""})
    return out
