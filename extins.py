# -*- coding: utf-8 -*-
"""Logică fără interfață pentru: clasificare mașini (tip facturare), mișcări anvelope, sezoane / extra depozitare,
comenzi anvelope și potrivirea recepțiilor lui Beti. Folosit de streamlit_app.py și testat separat."""
import json
import re
from datetime import date, datetime

import pandas as pd

# --- tipuri de facturare -----------------------------------------------------------------------------------------
BT_ARVAL, BT_HERTZ, BT_GY = "LEASING_ARVAL", "LEASING_HERTZ", "LEASING_ALT"
BT_PJ, BT_PF, BT_NONE = "CLIENT_MADYT_PJ", "PF", "NECLASIFICAT"
BILLING_TYPES = [BT_ARVAL, BT_HERTZ, BT_GY, BT_PJ, BT_PF, BT_NONE]
BT_RO = {BT_ARVAL: "Leasing ARVAL", BT_HERTZ: "Leasing HERTZ (Autotehnica Fleet Services)",
         BT_GY: "Alt leasing (GY Fleet)", BT_PJ: "Client MADYT – firmă (PJ)", BT_PF: "Client MADYT – persoană fizică",
         BT_NONE: "NECLASIFICAT"}
BT_COLOR = {BT_ARVAL: "#0b5394", BT_HERTZ: "#b8860b", BT_GY: "#6a1b9a", BT_PJ: "#0a7d32", BT_PF: "#2e7d32",
            BT_NONE: "#9e9e9e"}
LEASING_TYPES = (BT_ARVAL, BT_HERTZ, BT_GY)
HERTZ_FLEET = "Autotehnica Fleet Services SRL"
ARVAL_FLEET = "ARVAL SERVICE LEASE ROMANIA SRL"


def is_leasing(bt):
    return bt in LEASING_TYPES


def default_type(fleet, gy_fleets=()):
    """Tip implicit din numele flotei: ARVAL / Autotehnica(Hertz) / altă flotă GY / necunoscut -> NECLASIFICAT."""
    f = str(fleet or "").strip().upper()
    if not f:
        return BT_NONE
    if "ARVAL" in f:
        return BT_ARVAL
    if "AUTOTEHNICA" in f or "HERTZ" in f:
        return BT_HERTZ
    if f in {str(x).strip().upper() for x in gy_fleets if str(x).strip()}:
        return BT_GY
    return BT_NONE


def bill_via(bt):
    return "MY_WAY / GY" if is_leasing(bt) else "DIRECT"


# --- mișcări -------------------------------------------------------------------------------------------------------
MV_IN, MV_MOUNT, MV_OUT_CAR, MV_SCRAP, MV_LEFT = "PRIMIT", "MONTAT", "SCOS_HOTEL", "CASAT", "PLECAT"
MOVE_TYPES = [MV_IN, MV_MOUNT, MV_OUT_CAR, MV_SCRAP, MV_LEFT]
MOVE_RO = {MV_IN: "📥 Primit (curier / furnizor / leasing)", MV_MOUNT: "🔧 Montat pe mașină",
           MV_OUT_CAR: "🛞➡️🏨 Scos de pe mașină → hotel", MV_SCRAP: "♻️ Casat", MV_LEFT: "🚚 Plecat (relocat / ridicat)"}
MS_HOTEL, MS_NEW, MS_STOCK = "DIN_HOTEL", "NOI_CURIER", "STOC_PROPRIU"
MOUNT_SOURCES = [MS_HOTEL, MS_NEW, MS_STOCK]
MOUNT_RO = {MS_HOTEL: "din hotel", MS_NEW: "noi venite prin curier", MS_STOCK: "din stoc propriu", "": "-"}
MST_OK, MST_PROP, MST_CANC = "CONFIRMAT", "PROPUS", "ANULAT"
ORIGINS = ["FISA", "EMAIL", "MANUAL", "APLICATIE", "MIGRARE"]


def move_summary(moves):
    """Rezumatul pe mașină: anvelope primite / montate / scoase → hotel / casate / plecate + AWB-uri."""
    m = moves[moves["State"].replace("", MST_OK) == MST_OK] if len(moves) else moves
    out = {}
    for t in MOVE_TYPES:
        sub = m[m["Type"] == t] if len(m) else m
        out[t] = int(sum(_int(q) for q in sub["Qty"])) if len(sub) else 0
    awbs = [a for a in (m["AWB"] if len(m) else []) if str(a).strip()]
    out["AWB"] = list(dict.fromkeys(awbs))
    return out


def _int(x, default=0):
    try:
        return int(float(str(x).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return default


# --- sezoane --------------------------------------------------------------------------------------------------------
SEASON_DEFAULTS = {"SEZON_IARNA_START": "10-01", "SEZON_IARNA_END": "12-31",
                   "SEZON_VARA_START": "03-01", "SEZON_VARA_END": "06-15"}
SETTINGS_DEFAULTS = dict(SEASON_DEFAULTS, **{
    "DEPOZITARE_INCLUSA_LUNI": "6",
    "FURNIZORI": "",  # listă separată prin ";" – se completează de Mihai (4-5 furnizori)
    "MISCARI_DE_LA": "",
})
SETTINGS_NOTES = {
    "SEZON_IARNA_START": "Început fereastră schimb IARNĂ (LL-ZZ)", "SEZON_IARNA_END": "Sfârșit fereastră schimb IARNĂ (LL-ZZ)",
    "SEZON_VARA_START": "Început fereastră schimb VARĂ (LL-ZZ)", "SEZON_VARA_END": "Sfârșit fereastră schimb VARĂ (LL-ZZ)",
    "DEPOZITARE_INCLUSA_LUNI": "Depozitarea obișnuită inclusă în schimb (luni)",
    "FURNIZORI": "Furnizori anvelope, separați prin ;",
    "MISCARI_DE_LA": "Data de la care istoricul e ținut și în «Miscari» (setată automat)",
}


def _mmdd(s, fallback):
    m = re.match(r"^\s*(\d{1,2})[-./](\d{1,2})\s*$", str(s or ""))
    if not m:
        m = re.match(r"^\s*(\d{1,2})[-./](\d{1,2})\s*$", fallback)
    return int(m.group(1)), int(m.group(2))


def season_window(kind, year, settings=None):
    """kind 'IARNA'/'VARA', anul ferestrei -> (start, end) ca date."""
    s = dict(SEASON_DEFAULTS, **(settings or {}))
    a = _mmdd(s.get(f"SEZON_{kind}_START"), SEASON_DEFAULTS[f"SEZON_{kind}_START"])
    b = _mmdd(s.get(f"SEZON_{kind}_END"), SEASON_DEFAULTS[f"SEZON_{kind}_END"])
    start = date(year, a[0], a[1])
    end = date(year, b[0], b[1])
    if end < start:  # fereastră peste anul nou
        end = date(year + 1, b[0], b[1])
    return start, end


def season_label(kind, year):
    return f"{kind} {year}"


def seasons_list(today=None, settings=None, back=4):
    """Ultimele sezoane (cel curent sau cel mai recent început primul)."""
    today = today or date.today()
    out = []
    for y in range(today.year + 1, today.year - 3, -1):
        for k in ("IARNA", "VARA"):
            a, b = season_window(k, y, settings)
            if a <= today:
                out.append((season_label(k, y), k, y, a, b))
    out.sort(key=lambda x: x[3], reverse=True)
    return out[:back]


def parse_season_label(label):
    k, y = str(label).split()
    return k, int(y)


def _d(s):
    s = str(s or "").strip()
    if not s:
        return None
    s10 = s.split(" ")[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s10, fmt).date()
        except ValueError:
            continue
    return None


def extra_storage(season, hotel, receptions, moves, classify, settings=None, billed=None, today=None,
                  in_status=("DEPOZITAT", "DECIZIE_GY_ASTEPTATA"), norm=lambda x: x):
    """Lista EXTRA DEPOZITARE pentru un sezon.
    (a) seturi în hotel a căror mașină NU a avut schimb în fereastra sezonului (ultimul schimb înainte de început);
    (b) seturi primite (curier / relocate) și nemontate – inclusiv cele plecate ulterior – zile de la primire la plecare.
    classify(plate, fleet) -> dict(BillingType, ClientName, LeasingCompany, UserCompany).
    billed: set de chei (Season|plate|ref) deja generate în «Facturare». Întoarce DataFrame."""
    today = today or date.today()
    kind, year = parse_season_label(season)
    a, b = season_window(kind, year, settings)
    ref_end = min(today, b)
    billed = billed or set()
    mounted_in = set()
    if len(moves):
        for _, m in moves.iterrows():
            d = _d(m.get("Date"))
            if m.get("Type") == MV_MOUNT and d and a <= d <= b and m.get("State", "") in ("", MST_OK):
                mounted_in.add(norm(m.get("RegistrationNumber")))
    rows = []
    for _, h in hotel.iterrows():
        if h.get("Status") not in in_status:
            continue
        plate = norm(h.get("RegistrationNumber"))
        since = _d(h.get("StorageDate"))
        if not plate or since is None or since >= a or plate in mounted_in:
            continue
        c = classify(plate, h.get("FleetName", ""))
        rows.append(_extra_row(season, plate, c, h.get("Tyres", ""), since, ref_end, "HOTEL", f"HOTEL:{plate}",
                               "Set în hotel, fără schimb în sezon"))
    for _, r in receptions.iterrows():
        st_ = str(r.get("Status", "")).upper()
        if st_ not in ("RECEPTIONAT", "EXTRA_DEPOZITARE", "PLECAT"):
            continue
        since = _d(r.get("ReceptionDate"))
        if since is None or since > b:
            continue
        left = _d(r.get("LeftDate"))
        if st_ == "PLECAT" and left is not None and left < a and since < a:
            continue  # plecat înainte de sezon – aparține sezonului anterior
        until = left or ref_end
        plate = norm(r.get("RegistrationNumber")) or f"VIN {r.get('VIN', '')}"
        c = classify(plate, r.get("FleetName", ""))
        why = "Primit, nemontat" + (f", plecat {left} (AWB {r.get('LeftAWB', '') or '-'})" if left else "")
        rows.append(_extra_row(season, plate, c, r.get("Tyres", ""), since, until, "RECEPTIE",
                               f"REC:{r.get('ReceptionId', '')}", why))
    df = pd.DataFrame(rows, columns=EXTRA_COLS)
    if len(df):
        df["AlreadyBilled"] = [f"{season}|{p}|{ref}" in billed for p, ref in zip(df["RegistrationNumber"], df["Ref"])]
    else:
        df["AlreadyBilled"] = []
    return df


EXTRA_COLS = ["Season", "RegistrationNumber", "BillingType", "ClientName", "LeasingCompany", "UserCompany", "Tyres",
              "Since", "Until", "Days", "BillTo", "Via", "Source", "Ref", "Reason"]


def _extra_row(season, plate, c, tyres, since, until, source, ref, why):
    bt = c.get("BillingType", BT_NONE)
    bill_to = (f"GY Fleet / My Way – {c.get('LeasingCompany') or BT_RO[bt]}" if is_leasing(bt)
               else (c.get("ClientName") or "(client necunoscut – clasifică mașina)"))
    return {"Season": season, "RegistrationNumber": plate, "BillingType": bt, "ClientName": c.get("ClientName", ""),
            "LeasingCompany": c.get("LeasingCompany", ""), "UserCompany": c.get("UserCompany", ""), "Tyres": str(tyres),
            "Since": since.isoformat(), "Until": until.isoformat(), "Days": max(0, (until - since).days),
            "BillTo": bill_to, "Via": bill_via(bt), "Source": source, "Ref": ref, "Reason": why}


# --- comenzi --------------------------------------------------------------------------------------------------------
O_OFFER, O_ACC, O_ORD, O_SINV, O_RCV, O_MNT, O_TOBILL, O_BILLED, O_CANC = (
    "OFERTA", "ACCEPTATA", "COMANDATA", "FACTURA_FURNIZOR", "RECEPTIONATA", "MONTATA", "DE_FACTURAT", "FACTURATA",
    "ANULATA")
ORDER_FLOW = [O_OFFER, O_ACC, O_ORD, O_SINV, O_RCV, O_MNT, O_TOBILL, O_BILLED]
ORDER_RO = {O_OFFER: "1. Ofertă", O_ACC: "2. Acceptată de client", O_ORD: "3. Comandată la furnizor",
            O_SINV: "4. Factură furnizor (SPV)", O_RCV: "5. Sosită / recepționată", O_MNT: "6. Montată",
            O_TOBILL: "7. De facturat", O_BILLED: "8. Facturată", O_CANC: "Anulată"}
ORDER_OPEN_NOT_ARRIVED = (O_ACC, O_ORD, O_SINV)
ARR_OK, ARR_PROBLEM = "OK", "PROBLEMA"


def variants_from_json(s):
    try:
        v = json.loads(s) if str(s).strip() else []
        return v if isinstance(v, list) else []
    except ValueError:
        return []


def variants_to_json(vs):
    return json.dumps(vs, ensure_ascii=False)


def norm_dim(s):
    """'205/65 R16 95H' -> '2056516' (lățime, profil, diametru) – pentru potrivire."""
    s = str(s or "").upper()
    m = re.search(r"(\d{3})\s*[/ ]\s*(\d{2})\s*Z?R?\s*F?\s*(\d{2})", s)
    if m:
        return "".join(m.groups())
    return re.sub(r"[^0-9]", "", s)[:7]


def norm_name(s):
    s = re.sub(r"\b(S\.?R\.?L\.?|S\.?A\.?|SRL|SA|ROMANIA)\b", " ", str(s or "").upper())
    return re.sub(r"[^A-Z0-9]", "", s)


def parse_reception_paste(text):
    """Text lipit de Beti (din Excel/SPV): Furnizor, Factură, Dimensiune, Buc[, Marcă/model]. Separatori: tab ; |.
    Rândul de antet (dacă există) e ignorat. Întoarce listă de dicturi."""
    out = []
    for line in str(text or "").splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in re.split(r"\t|;|\|", line)]
        if len(parts) < 4 and "," in line:
            parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            out.append({"Supplier": "", "Invoice": "", "Dimension": line.strip(), "Qty": 0, "Extra": "",
                        "Error": "rând incomplet (trebuie: furnizor; factură; dimensiune; bucăți)"})
            continue
        sup, inv, dim, qty = parts[:4]
        if norm_dim(dim) == "" and not re.search(r"\d", qty):
            continue  # antet
        out.append({"Supplier": sup, "Invoice": inv, "Dimension": dim, "Qty": _int(qty),
                    "Extra": " ".join(parts[4:]), "Error": ""})
    return out


def match_receptions(lines, orders):
    """Potrivește rândurile lipite cu comenzile deschise (COMANDATA / FACTURA_FURNIZOR fără sosire).
    Criterii: furnizor (nume normalizat, conținut), dimensiune normalizată, bucăți egale. Unu-la-unu.
    Întoarce (potrivite: [(line, OrderId)], nepotrivite: [line])."""
    cand = orders[orders["Status"].isin([O_ORD, O_SINV, O_ACC])] if len(orders) else orders
    used, matched, unmatched = set(), [], []
    for ln in lines:
        if ln.get("Error"):
            unmatched.append(ln)
            continue
        ns, nd = norm_name(ln["Supplier"]), norm_dim(ln["Dimension"])
        best = None
        for _, o in cand.iterrows():
            if o["OrderId"] in used:
                continue
            os_ = norm_name(o.get("Supplier", ""))
            if not os_ or not ns or not (os_ in ns or ns in os_):
                continue
            if norm_dim(o.get("Dimension", "")) != nd:
                continue
            if _int(o.get("Qty")) != _int(ln["Qty"]):
                continue
            # prioritate: aceeași factură deja înregistrată, apoi cea mai veche comandă
            score = (0 if str(o.get("SupplierInvoice", "")).strip() == ln["Invoice"] else 1, str(o.get("OrderedDate", "")))
            if best is None or score < best[0]:
                best = (score, o["OrderId"])
        if best:
            used.add(best[1])
            matched.append((ln, best[1]))
        else:
            unmatched.append(ln)
    return matched, unmatched
