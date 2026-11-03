# -*- coding: utf-8 -*-
"""
MADYT Autoserv – Gestiune Hotel Anvelope (format GY Fleet, o linie = o anvelopă)

Foi folosite în tabelul Google Sheets:
  - 'Inventar GY'      : exportul original GY Fleet. Aplicația DOAR îl citește (migrare), nu îl modifică.
  - 'Hotel_Anvelope'   : anvelopele aflate acum în hotel, câte un rând pe anvelopă, exact coloanele GY.
  - 'Hotel'            : câte un rând pe mașină (set): poziție raft, status, dată depozitare/schimb.
  - 'Pozitii'          : pozițiile de raft R-N-P și flota căreia îi aparțin.
  - 'Istoric'          : toate operațiunile (RECEPTIE / SCHIMB / IESIRE / IMPORT).
  - 'Arhiva_Anvelope'  : anvelopele scoase din hotel (montate la schimb sau ridicate), cu data și motivul.
  - 'Receptii'         : seturile trimise de leasing (GY Fleet) pentru o mașină anume, câte un rând pe recepție.
  - 'Receptii_Anvelope': anvelopele fiecărei recepții de leasing, câte un rând pe anvelopă (legate prin ReceptionId).
  - 'Fise_GY'          : fișele de lucru GY pentru facturare (schimb + depozitare / extra depozitare) și statusul lor.
Sau, în modul DEMO, fișiere CSV locale cu aceleași nume.
"""
import csv
import io
import os
import re
from collections import Counter
from datetime import date, datetime

import pandas as pd

import receptii_import as rimp
import streamlit as st

st.set_page_config(page_title="MADYT – Hotel Anvelope", page_icon="🛞", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# Constante
# ---------------------------------------------------------------------------
DEFAULT_SPREADSHEET_ID = "1qs5DuQ4--vT0Tr91sqH2om4B1dHM_-IyNLnkcvL5leA"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

SRC = "Inventar GY"
TY = "Hotel_Anvelope"
HOTEL = "Hotel"
POZ = "Pozitii"
IST = "Istoric"
ARH = "Arhiva_Anvelope"

NOTE = "StorageNote(Comments/AccessoriesStored)"
# Coloanele GY Fleet în ordinea exactă. Al doilea 'CITY' (orașul service-ului) e ținut intern ca 'CITY_2'.
GY_COLS = ["SOLD-TO", "FleetName", "CITY", "RegistrationNumber", "Fleet VIN", "Chassis Num", "Make/Model",
           "SHIP-TO", "ServiceProviderName", "CITY_2", "MaterialNumber", "BRAND", "ProductGroup",
           "MaterialDescription", "QUANTITY", "StorageDate", "TreadDepth", "DOT", "WheelType",
           "ServiceProviderStorageLocation", NOTE]
GY_HEADER = [("CITY" if c == "CITY_2" else c) for c in GY_COLS]  # antetul real, cu CITY de două ori
VEHICLE_COLS = ["SOLD-TO", "FleetName", "CITY", "RegistrationNumber", "Fleet VIN", "Chassis Num", "Make/Model",
                "SHIP-TO", "ServiceProviderName", "CITY_2"]
HOTEL_COLS = ["RegistrationNumber", "FleetName", "PositionCode", "Status", "StorageDate", "ExitDate", "Season",
              "LegacyLocation", "Phone", "Email", "Note", "UserName", "UserPhone", "ClientCompany", "VIN"]
CAR_PEOPLE = ["UserName", "UserPhone", "ClientCompany"]  # utilizator mașină + firma client cu contract de leasing
DEFAULT_FLEETS = ["ARVAL SERVICE LEASE ROMANIA SRL", "Autotehnica Fleet Services SRL", "HERTZ"]
POZ_COLS = ["PositionCode", "Row", "Level", "Leg", "FleetName", "OccupiedPlate"]
IST_COLS = ["Timestamp", "RegistrationNumber", "Action", "Details", "PositionCode", "UserNote", "Operator"]
ARH_COLS = ["ArchivedAt", "Reason"] + GY_COLS
REC = "Receptii"
RTY = "Receptii_Anvelope"
FISE = "Fise_GY"
REC_COLS = rimp.REC_COLS  # definite în receptii_import.py (folosite și de scripts/import_receptie.py)
RTY_COLS = rimp.RTY_COLS
FISE_COLS = ["FisaId", "ReceptionId", "RegistrationNumber", "FleetName", "Type", "Status", "CreatedDate", "SentDate",
             "ApprovedDate", "RejectedDate", "InvoicedDate", "GYRef", "Note", "Operator"]
SCHEMAS = {TY: GY_COLS, HOTEL: HOTEL_COLS, POZ: POZ_COLS, IST: IST_COLS, ARH: ARH_COLS,
           REC: REC_COLS, RTY: RTY_COLS, FISE: FISE_COLS}

# Recepții leasing
RC_OPEN = "RECEPTIONAT"
RC_SWAP = "SCHIMBAT"
RC_EXTRA = "EXTRA_DEPOZITARE"
RC_DAYS = 90  # sfârșit de sezon: max ~3 luni de la recepție
AXLES = ["", "FS", "FD", "SS", "SD", "REZERVĂ"]
# Fișe GY (facturarea se face doar după aprobarea GY)
F_TODO, F_SENT, F_OK, F_REJ, F_INV = "DE_INTRODUS_GY", "TRIMIS_GY", "APROBAT_GY", "RESPINS_GY", "FACTURAT"
F_STATUSES = [F_TODO, F_SENT, F_OK, F_REJ, F_INV]
F_RO = {F_TODO: "De introdus în GY", F_SENT: "Trimisă în GY", F_OK: "Aprobată GY (de facturat)",
        F_REJ: "Respinsă GY", F_INV: "Facturată"}
F_DATE = {F_SENT: "SentDate", F_OK: "ApprovedDate", F_REJ: "RejectedDate", F_INV: "InvoicedDate", F_TODO: ""}
F_NEXT = {F_TODO: [F_SENT], F_SENT: [F_OK, F_REJ], F_REJ: [F_TODO, F_SENT], F_OK: [F_INV], F_INV: []}
FT_SWAP = "SCHIMB + DEPOZITARE"
FT_EXTRA = "EXTRA DEPOZITARE"

COMUN = "COMUN"
ST_DEP = "DEPOZITAT"
ST_RID = "RIDICAT"
SEASONS = ["Winter", "Summer", "All Season"]  # valorile GY din ProductGroup
SEASON_RO = {"Winter": "IARNA", "Summer": "VARA", "All Season": "ALL SEASON", "": "-"}
WHEEL_TYPES = ["Tyre Only", "Alloy", "Steel"]
WHEEL_RO = {"Tyre Only": "Fără jantă", "Alloy": "Jantă aliaj", "Steel": "Jantă tablă"}

DISPLAY = {
    "RegistrationNumber": "Număr auto", "FleetName": "Flotă / client", "Chassis Num": "VIN",
    "Make/Model": "Model", "BRAND": "Marcă", "ProductGroup": "Sezon", "MaterialDescription": "Anvelopă",
    "StorageDate": "Dată depozitare", "TreadDepth": "Profil (mm)", "DOT": "DOT", "WheelType": "Jantă",
    "ServiceProviderStorageLocation": "Locație veche GY", NOTE: "Observații", "PositionCode": "Poziție",
    "Status": "Status", "ExitDate": "Dată ieșire", "Season": "Sezon", "LegacyLocation": "Locație veche GY",
    "Phone": "Telefon", "Email": "Email", "Note": "Notă", "Row": "Rând", "Level": "Nivel", "Leg": "Picior",
    "OccupiedPlate": "Ocupat de", "Timestamp": "Data / ora", "Action": "Acțiune", "Details": "Detalii",
    "UserNote": "Notă", "Operator": "Operator", "Tyres": "Nr. anv.", "MinTread": "Profil minim",
    "Days": "Zile", "Brands": "Mărci", "Descriptions": "Anvelope", "DOTs": "DOT-uri", "CITY_2": "CITY (service)",
    "ReceptionId": "ID recepție", "ReceptionDate": "Dată recepție", "WaitingLocation": "Locație așteptare",
    "SwapDate": "Dată schimb", "MyWayDate": "Dată My Way", "TyreNo": "Nr.", "TyreModel": "Model anvelopă",
    "Axle": "Poziție pe mașină", "FisaId": "ID fișă", "Type": "Tip", "CreatedDate": "Creată",
    "SentDate": "Trimisă GY", "ApprovedDate": "Aprobată GY", "RejectedDate": "Respinsă GY",
    "InvoicedDate": "Facturată", "GYRef": "Nr. fișă GY", "CreatedAt": "Creat la",
    "UserName": "Utilizator", "UserPhone": "Telefon utilizator", "ClientCompany": "Firmă client",
    "VIN": "VIN", "Condition": "Stare (NOI/FOLOSITE)",
}

APP_DIR = os.path.dirname(os.path.abspath(__file__))


class BackendError(Exception):
    """Eroare prietenoasă afișată utilizatorului."""


# ---------------------------------------------------------------------------
# Configurare
# ---------------------------------------------------------------------------
def _secret(key, default=None):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:  # noqa: BLE001
        pass
    return default


def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "da", "on")


def get_cfg():
    def num(key, env, default, cast):
        try:
            return cast(_secret(key, os.environ.get(env, default)))
        except Exception:  # noqa: BLE001
            return default

    return {
        "demo": _truthy(_secret("demo_mode", os.environ.get("MADYT_DEMO", "0"))),
        "spreadsheet_id": str(_secret("spreadsheet_id", os.environ.get("MADYT_SPREADSHEET_ID",
                                                                       DEFAULT_SPREADSHEET_ID))).strip(),
        "source_sheet": str(_secret("source_sheet", os.environ.get("MADYT_SOURCE_SHEET", SRC))),
        "worn_mm": num("worn_threshold_mm", "MADYT_WORN_MM", 3.0, float),
        "days": num("storage_days_limit", "MADYT_STORAGE_DAYS", 180, int),
        "demo_dir": str(_secret("demo_data_dir", os.environ.get("MADYT_DEMO_DIR", os.path.join(APP_DIR, "demo_data")))),
    }


CFG = get_cfg()


# ---------------------------------------------------------------------------
# Conversii și utilitare
# ---------------------------------------------------------------------------
def values_to_df(vals):
    """Listă de rânduri (prima = antet) -> DataFrame de text. Antetele duplicate primesc _2, _3 (CITY -> CITY_2)."""
    if not vals:
        return pd.DataFrame()
    header, seen = [], Counter()
    for i, h in enumerate(vals[0]):
        h = str(h).strip() or f"Coloana_{i + 1}"
        seen[h] += 1
        header.append(h if seen[h] == 1 else f"{h}_{seen[h]}")
    n = len(header)
    rows = []
    for r in vals[1:]:
        r = [str(x) for x in (list(r) + [""] * n)[:n]]
        if any(x.strip() for x in r):
            rows.append(r)
    return pd.DataFrame(rows, columns=header, dtype=str)


def norm_plate(p):
    return re.sub(r"[^A-Z0-9]", "", str(p).upper())


def today_s():
    return date.today().isoformat()


def now_s():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def us_date(d):
    return f"{d.month}/{d.day}/{d.year}"


def parse_date(s):
    """Acceptă 2026-11-02, 12/29/2023 (format GY, lună/zi/an), 29.12.2023."""
    s = str(s).strip()
    if not s:
        return pd.NaT
    s10 = s.split(" ")[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%y"):
        try:
            return pd.Timestamp(datetime.strptime(s10, fmt))
        except ValueError:
            continue
    return pd.to_datetime(s, errors="coerce")


def parse_mm(s):
    """'5,0' -> 5.0 ; '6/6/5/4' -> 4.0 (cea mai mică valoare)."""
    s = str(s).strip()
    if re.fullmatch(r"\d+,\d+", s):
        s = s.replace(",", ".")
    vals = []
    for n in re.findall(r"\d+(?:[.,]\d+)?", s):
        try:
            vals.append(float(n.replace(",", ".")))
        except ValueError:
            pass
    vals = [v for v in vals if v < 30]
    return min(vals) if vals else None


def fmt_mm(s):
    """Profil în formatul GY: '5,0'."""
    v = parse_mm(s)
    return f"{v:.1f}".replace(".", ",") if v is not None else str(s).strip()


def is_worn(tread):
    v = parse_mm(tread)
    return v is not None and v < CFG["worn_mm"]


def norm_season(s):
    k = re.sub(r"[^a-z]", "", str(s).lower())
    if k in ("winter", "iarna"):
        return "Winter"
    if k in ("summer", "vara"):
        return "Summer"
    if k.startswith("all") or "4season" in k:
        return "All Season"
    return str(s).strip()


def other_season(s):
    return {"Winter": "Summer", "Summer": "Winter"}.get(norm_season(s), "Winter")


def ensure_schema(df, cols):
    df = df.copy() if df is not None else pd.DataFrame()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    extras = [c for c in df.columns if c not in cols]
    return df[cols + extras].fillna("").astype(str).reset_index(drop=True)


def uniq(values):
    out = []
    for v in values:
        v = str(v).strip()
        if v and v not in out:
            out.append(v)
    return out


def pos_sort_key(code):
    m = re.match(r"R(\d+)-N(\d+)-P(\d+)", str(code))
    return tuple(int(x) for x in m.groups()) if m else (9999, 9999, 9999)


def sort_positions(pos):
    if pos.empty:
        return pos
    order = sorted(range(len(pos)), key=lambda i: pos_sort_key(pos.iloc[i]["PositionCode"]))
    return pos.iloc[order].reset_index(drop=True)


def int_key(x):
    return int(x) if str(x).isdigit() else 0


def show_df(df, rename=True, height=None):
    d = df.rename(columns=DISPLAY) if rename else df
    kw = {"hide_index": True}
    if height:
        kw["height"] = height
    try:
        st.dataframe(d, width="stretch", **kw)
    except Exception:  # noqa: BLE001
        st.dataframe(d, use_container_width=True, **kw)


def flash(msg, kind="success"):
    st.session_state.setdefault("_flash", []).append((kind, msg))
    st.session_state["_ver"] = st.session_state.get("_ver", 0) + 1  # resetează tabelele editabile după salvare


def ver():
    return st.session_state.get("_ver", 0)


# ---------------------------------------------------------------------------
# Backend DEMO (fișiere CSV)
# ---------------------------------------------------------------------------
class DemoBackend:
    label = "DEMO – fișiere CSV locale (fără Google)"
    sa_email = ""

    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        if not os.listdir(folder):
            seed_demo(self)

    def _path(self, name):
        return os.path.join(self.folder, f"{name}.csv")

    def exists(self, name):
        return os.path.exists(self._path(name))

    def _values(self, name):
        with open(self._path(name), newline="", encoding="utf-8") as f:
            return list(csv.reader(f))

    def read(self, name):
        return values_to_df(self._values(name)) if self.exists(name) else pd.DataFrame()

    def read_source(self, name):
        if self.exists(name):
            return values_to_df(self._values(name)), name
        return pd.DataFrame(), ""

    def write_values(self, name, values):
        with open(self._path(name), "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(values)

    def write(self, name, df):
        self.write_values(name, [list(df.columns)] + df.astype(str).values.tolist())

    def ensure_header(self, name, cols):
        """Adaugă la capătul antetului coloanele lipsă (fără a reordona sau atinge datele)."""
        if not self.exists(name):
            return []
        vals = self._values(name)
        head = vals[0] if vals else []
        missing = [c for c in cols if c not in head]
        if missing:
            vals = [head + missing] + [r + [""] * len(missing) for r in vals[1:]] if vals else [missing]
            self.write_values(name, vals)
        return missing

    def append_many(self, name, rows, cols):
        if not rows:
            return
        new = not self.exists(name)
        with open(self._path(name), "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(cols)
            w.writerows([[str(x) for x in r] for r in rows])


# ---------------------------------------------------------------------------
# Backend Google Sheets
# ---------------------------------------------------------------------------
class GSheetBackend:
    def __init__(self, spreadsheet_id):
        import gspread
        from google.oauth2.service_account import Credentials

        self._gs = gspread
        info = _secret("gcp_service_account")
        self.sa_email = ""
        if info:
            info = dict(info)
            self.sa_email = info.get("client_email", "")
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
        else:
            path = (_secret("gcp_service_account_file") or os.environ.get("MADYT_SA_FILE")
                    or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
            if not path:
                raise BackendError(
                    "Nu am găsit cheia contului de serviciu Google. Adaugă secțiunea [gcp_service_account] în "
                    "secrets (Streamlit Cloud → Settings → Secrets) sau setează 'gcp_service_account_file' / "
                    "variabila MADYT_SA_FILE cu calea spre fișierul JSON.")
            if not os.path.isabs(path):
                path = os.path.join(APP_DIR, path)
            if not os.path.exists(path):
                raise BackendError(f"Fișierul cheii JSON nu există: {path}")
            creds = Credentials.from_service_account_file(path, scopes=SCOPES)
            self.sa_email = getattr(creds, "service_account_email", "")
        self.label = f"Google Sheets ({spreadsheet_id[:10]}…)"
        gc = gspread.authorize(creds)
        try:
            self.sh = gc.open_by_key(spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            raise BackendError(
                "Tabelul Google Sheets nu a fost găsit sau nu este partajat cu contul de serviciu. Partajează "
                f"tabelul (Share) cu emailul {self.sa_email or '(client_email din JSON)'} ca Editor.")
        except gspread.exceptions.APIError as e:
            raise BackendError(f"Google a refuzat accesul ({e}). Verifică dacă Google Sheets API și Google Drive "
                               f"API sunt activate și dacă tabelul e partajat cu {self.sa_email}.")

    def _ws(self, name):
        """Foile sunt ținute în memorie (o singură cerere de metadate) – evită limita Google de citiri/minut."""
        cache = getattr(self, "_wsc", None)
        if cache is None or name not in cache:
            cache = self._wsc = {w.title: w for w in self.sh.worksheets()}
        return cache.get(name)

    def exists(self, name):
        return self._ws(name) is not None

    def read(self, name):
        ws = self._ws(name)
        return values_to_df(ws.get_all_values()) if ws is not None else pd.DataFrame()

    def read_source(self, name):
        """Citește foaia sursă GY după nume; dacă nu există, prima foaie (dacă nu e una de-a aplicației)."""
        ws = self._ws(name)
        if ws is None:
            ws = self.sh.get_worksheet(0)
            if ws is None or ws.title in SCHEMAS:
                return pd.DataFrame(), ""
        return values_to_df(ws.get_all_values()), ws.title

    def write_values(self, name, values):
        from gspread.utils import rowcol_to_a1

        nrows, ncols = len(values), max(1, len(values[0]) if values else 1)
        self._wsc = None  # dimensiuni proaspete (rânduri adăugate între timp)
        ws = self._ws(name)
        if ws is None:
            ws = self.sh.add_worksheet(title=name, rows=max(100, nrows + 20), cols=max(10, ncols))
            self._wsc = None
        if ws.row_count < nrows or ws.col_count < ncols:
            ws.resize(rows=max(ws.row_count, nrows + 20), cols=max(ws.col_count, ncols))
        ws.update(range_name="A1", values=values, value_input_option="RAW")
        if ws.row_count > nrows:
            ws.batch_clear([f"A{nrows + 1}:{rowcol_to_a1(ws.row_count, ws.col_count)}"])

    def write(self, name, df):
        if name not in SCHEMAS or name == CFG["source_sheet"]:
            raise BackendError("Foaia sursă GY nu se modifică din aplicație.")
        self.write_values(name, [list(df.columns)] + df.astype(str).values.tolist())

    def ensure_header(self, name, cols):
        """Adaugă la capătul antetului coloanele lipsă (doar celulele din rândul 1, fără a reordona)."""
        from gspread.utils import rowcol_to_a1

        if name == CFG["source_sheet"] or name not in SCHEMAS:
            return []
        ws = self._ws(name)
        if ws is None:
            return []
        head = ws.row_values(1)
        missing = [c for c in cols if c not in head]
        if missing:
            start = len(head) + 1
            if ws.col_count < len(head) + len(missing):
                ws.resize(cols=len(head) + len(missing))
            ws.update(range_name=rowcol_to_a1(1, start), values=[missing], value_input_option="RAW")
        return missing

    def append_many(self, name, rows, cols):
        if not rows:
            return
        ws = self._ws(name)
        if ws is None:
            ws = self.sh.add_worksheet(title=name, rows=100, cols=max(10, len(cols)))
            self._wsc = None
            ws.update(range_name="A1", values=[cols], value_input_option="RAW")
        ws.append_rows([[str(x) for x in r] for r in rows], value_input_option="RAW")


# ---------------------------------------------------------------------------
# Date demo (fictive, în formatul real GY Fleet)
# ---------------------------------------------------------------------------
def demo_gy_rows():
    def tyre(sold, fleet, plate, vin, model, mat, brand, season, desc, sdate, tread, dot, wheel="Tyre Only",
             loc="D", note=""):
        return [sold, fleet, "Bucuresti", plate, "", vin, model, "0030999999", "MADYT Autoserv", "Buftea, Ilfov",
                mat, brand, season, desc, "1", sdate, tread, dot, wheel, loc, note]

    rows = []
    for t, d in [("6,0", "3823"), ("6,0", "3823"), ("5,0", "1224"), ("7,0", "1224")]:
        rows.append(tyre("0030000001", "LEASING DEMO SRL", "B101DEM", "VF1DEMO0000000001", "DACIA LOGAN",
                         "000000000000111111", "GOODYEAR", "Winter", "185/65R15 88T ULTRAGRIP 9", "12/29/2023", t, d))
    for t, d, n in [("7,0", "0925", ""), ("7,0", "0925", ""), ("2,5", "4419", "ANV ARE PETIC"), ("7,0", "0925", "")]:
        rows.append(tyre("0030000001", "LEASING DEMO SRL", "B102DEM", "WVWDEMO0000000002", "VOLKSWAGEN GOLF",
                         "000000000000222222", "MICHELIN", "Summer", "205/55R16 91V PRIMACY 4", "4/22/2026", t, d,
                         note=n))
    for _ in range(4):
        rows.append(tyre("0030000002", "FLOTA TEST SRL", "XB203TST", "TMBDEMO0000000003", "? N/A",
                         "000000000000333333", "FULDA", "Winter", "205/60R16 96H KRI CONTROL HP 2 XL", "6/22/2026",
                         "8,0", "3024", wheel="Alloy", loc=""))
    return rows


def seed_demo(be):
    be.write_values(SRC, [GY_HEADER] + demo_gy_rows())
    pos = []
    for r, fleet in [(1, "LEASING DEMO SRL"), (2, COMUN), (3, COMUN)]:
        for n in range(1, 4):
            for p in range(1, 5):
                pos.append([f"R{r}-N{n}-P{p}", str(r), str(n), str(p), fleet, ""])
    be.write(POZ, pd.DataFrame(pos, columns=POZ_COLS))


# ---------------------------------------------------------------------------
# Acces la date
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_backend(demo, spreadsheet_id, demo_dir):
    return DemoBackend(demo_dir) if demo else GSheetBackend(spreadsheet_id)


def backend():
    return get_backend(CFG["demo"], CFG["spreadsheet_id"], CFG["demo_dir"])


def clean_gy(df):
    """Aduce un tabel GY la coloanele standard: plăcuțe normalizate, sezon GY, rânduri fără număr eliminate."""
    df = ensure_schema(df, GY_COLS)
    df = df[[c for c in GY_COLS]].copy()
    for c in GY_COLS:
        df[c] = df[c].str.strip()
    df["RegistrationNumber"] = df["RegistrationNumber"].map(norm_plate)
    df["ProductGroup"] = df["ProductGroup"].map(lambda s: norm_season(s) if s else "")
    skipped = int((df["RegistrationNumber"] == "").sum())
    return df[df["RegistrationNumber"] != ""].reset_index(drop=True), skipped


def hotel_from_tyres(ty):
    rows = []
    for plate, g in ty.groupby("RegistrationNumber", sort=False):
        dates = [d for d in g["StorageDate"].map(parse_date) if pd.notna(d)]
        rows.append({
            "RegistrationNumber": plate,
            "FleetName": Counter(g["FleetName"]).most_common(1)[0][0],
            "PositionCode": "", "Status": ST_DEP,
            "StorageDate": max(dates).strftime("%Y-%m-%d") if dates else "",
            "ExitDate": "", "Season": "/".join(uniq(g["ProductGroup"])),
            "LegacyLocation": ", ".join(uniq(g["ServiceProviderStorageLocation"])),
            "Phone": "", "Email": "", "Note": "",
        })
    return ensure_schema(pd.DataFrame(rows), HOTEL_COLS)


@st.cache_resource(show_spinner="Pregătesc foile de lucru…")
def initialize(demo, spreadsheet_id, demo_dir):
    be = get_backend(demo, spreadsheet_id, demo_dir)
    msgs = []
    if not be.exists(TY):
        src, title = be.read_source(CFG["source_sheet"])
        ty, skipped = clean_gy(src) if len(src) else (ensure_schema(pd.DataFrame(), GY_COLS), 0)
        be.write(TY, ty)
        if not be.exists(HOTEL):
            be.write(HOTEL, hotel_from_tyres(ty))
        msgs.append(
            f"Am creat foile aplicației din '{title or '(nicio foaie sursă)'}': {len(ty)} anvelope, "
            f"{ty['RegistrationNumber'].nunique()} mașini. Foaia '{title}' a rămas neatinsă."
            + (f" {skipped} rânduri fără număr auto (ex. rând de totaluri) au fost ignorate." if skipped else "")
            + " Seturile importate nu au încă poziție R-N-P; poziția se alege la primul schimb.")
    for name in (HOTEL, POZ, IST, ARH, REC, RTY, FISE):
        if not be.exists(name):
            be.write(name, pd.DataFrame(columns=SCHEMAS[name]))
    for name in (HOTEL, REC):
        try:
            be.ensure_header(name, SCHEMAS[name])
        except Exception:  # noqa: BLE001 – nu blocăm aplicația pentru antet
            pass
    return msgs


@st.cache_data(ttl=30, show_spinner=False)
def _cached_read(key, name):
    return backend().read(name)


def load(name, fresh=False):
    key = (CFG["demo"], CFG["spreadsheet_id"])
    df = ensure_schema(backend().read(name) if fresh else _cached_read(key, name), SCHEMAS[name])
    if name == HOTEL:
        df["Status"] = df["Status"].str.strip().str.upper()
        df["PositionCode"] = df["PositionCode"].str.strip().str.upper()
    if name == POZ:
        df["PositionCode"] = df["PositionCode"].str.strip().str.upper()
    if name == TY:
        df["_plate"] = df["RegistrationNumber"].map(norm_plate)
    return df


def clear_cache():
    _cached_read.clear()


def occupied_map(hotel):
    dep = hotel[(hotel["Status"] == ST_DEP) & (hotel["PositionCode"] != "")]
    return dict(zip(dep["PositionCode"], dep["RegistrationNumber"]))


def sync_positions(hotel, pos):
    pos = ensure_schema(pos, POZ_COLS)
    occ = occupied_map(hotel)
    pos["OccupiedPlate"] = pos["PositionCode"].map(lambda c: occ.get(str(c).strip(), ""))
    return pos


def save(hotel=None, ty=None, archive_rows=None, logs=None):
    """Scrie modificările: anvelope, hotel (+ ocuparea pozițiilor), arhivă, istoric."""
    be = backend()
    if ty is not None:
        be.write(TY, ensure_schema(ty.drop(columns=["_plate"], errors="ignore"), GY_COLS)[GY_COLS])
    if hotel is not None:
        be.write(HOTEL, ensure_schema(hotel, HOTEL_COLS))
        pos = load(POZ, fresh=True)
        if len(pos):
            be.write(POZ, sync_positions(hotel, pos))
    if archive_rows:
        be.append_many(ARH, archive_rows, ARH_COLS)
    if logs:
        be.append_many(IST, logs, IST_COLS)
    clear_cache()


def log_row(action, plate, details, code="", note=""):
    return [now_s(), plate, action, details, code, note, st.session_state.get("operator", "")]


# ---------------------------------------------------------------------------
# Logica seturilor (o mașină = un set de anvelope)
# ---------------------------------------------------------------------------
def find_row(hotel, plate, only_status=None):
    p = norm_plate(plate)
    if not p:
        return None
    mask = hotel["RegistrationNumber"].map(norm_plate) == p
    if only_status:
        mask &= hotel["Status"] == only_status
    idx = hotel.index[mask].tolist()
    if not idx:
        return None
    dep = [i for i in idx if hotel.at[i, "Status"] == ST_DEP]
    return dep[-1] if dep else idx[-1]


def tyres_of(ty, plate):
    return ty[ty["RegistrationNumber"].map(norm_plate) == norm_plate(plate)]


def set_days(hrow, tyres=None):
    d = parse_date(hrow.get("StorageDate", ""))
    if pd.isna(d) and tyres is not None and len(tyres):
        ds = [x for x in tyres["StorageDate"].map(parse_date) if pd.notna(x)]
        d = max(ds) if ds else pd.NaT
    return (pd.Timestamp(date.today()) - d).days if pd.notna(d) else None


def build_sets(hotel, ty):
    """Tabel cu câte un rând pe set DEPOZITAT (pentru căutare și rapoarte)."""
    dep = hotel[hotel["Status"] == ST_DEP]
    groups = {k: g for k, g in ty.groupby("_plate")} if len(ty) else {}
    rows = []
    for _, h in dep.iterrows():
        g = groups.get(norm_plate(h["RegistrationNumber"]), ty.iloc[0:0])
        treads = [v for v in g["TreadDepth"].map(parse_mm) if v is not None]
        rows.append({
            "RegistrationNumber": h["RegistrationNumber"], "FleetName": h["FleetName"],
            "PositionCode": h["PositionCode"], "LegacyLocation": h["LegacyLocation"],
            "Season": "/".join(SEASON_RO.get(s, s) for s in uniq(g["ProductGroup"])) or SEASON_RO.get(h["Season"], h["Season"]),
            "Tyres": len(g), "Brands": ", ".join(uniq(g["BRAND"])),
            "Descriptions": " | ".join(uniq(g["MaterialDescription"])),
            "MinTread": min(treads) if treads else None, "DOTs": ", ".join(g["DOT"]),
            "Make/Model": ", ".join(uniq(g["Make/Model"])), "Chassis Num": ", ".join(uniq(g["Chassis Num"])),
            "StorageDate": h["StorageDate"], "Days": set_days(h, g), NOTE: " | ".join(uniq(g[NOTE])),
            "Phone": h["Phone"], "UserName": h["UserName"], "UserPhone": h["UserPhone"],
            "ClientCompany": h["ClientCompany"],
        })
    cols = ["RegistrationNumber", "FleetName", "PositionCode", "LegacyLocation", "Season", "Tyres", "Brands",
            "Descriptions", "MinTread", "DOTs", "Make/Model", "Chassis Num", "StorageDate", "Days", NOTE, "Phone", "UserName", "UserPhone", "ClientCompany"]
    return pd.DataFrame(rows, columns=cols)


def vehicle_template(ty, plate, hrow=None):
    """Datele de vehicul/flotă pentru rândurile noi: din anvelopele existente ale mașinii sau valorile uzuale."""
    old = tyres_of(ty, plate)
    if len(old):
        return {c: old.iloc[0][c] for c in VEHICLE_COLS}
    tpl = {c: "" for c in VEHICLE_COLS}
    for c in ("SHIP-TO", "ServiceProviderName", "CITY_2", "CITY"):
        vals = [v for v in ty[c] if v] if len(ty) else []
        tpl[c] = Counter(vals).most_common(1)[0][0] if vals else ""
    tpl["ServiceProviderName"] = tpl["ServiceProviderName"] or "MADYT Autoserv"
    tpl["RegistrationNumber"] = norm_plate(plate)
    if hrow is not None:
        tpl["FleetName"] = hrow.get("FleetName", "")
    return tpl


def make_tyre_rows(tpl, tyres, legacy_loc=""):
    rows = []
    for t in tyres:
        r = dict(tpl)
        r.update({
            "MaterialNumber": t.get("MaterialNumber", ""), "BRAND": t.get("BRAND", "").strip().upper(),
            "ProductGroup": norm_season(t.get("ProductGroup", "")),
            "MaterialDescription": t.get("MaterialDescription", "").strip().upper(), "QUANTITY": "1",
            "StorageDate": us_date(date.today()), "TreadDepth": fmt_mm(t.get("TreadDepth", "")),
            "DOT": str(t.get("DOT", "")).strip(), "WheelType": t.get("WheelType", "Tyre Only"),
            "ServiceProviderStorageLocation": legacy_loc, NOTE: t.get(NOTE, "").strip(),
        })
        rows.append(r)
    return pd.DataFrame(rows, columns=GY_COLS)


def expand_tyres(common, n, per_tyre=None):
    """Setul dat jos: n anvelope; valorile goale per anvelopă se completează din valorile comune."""
    out = []
    for i in range(n):
        t = dict(common)
        if per_tyre is not None and i < len(per_tyre):
            for k, v in per_tyre[i].items():
                if str(v).strip() and str(v).strip().lower() not in ("nan", "none"):
                    t[k] = str(v).strip()
        out.append(t)
    return out


def validate_tyres(tyres):
    for i, t in enumerate(tyres, 1):
        if not t.get("MaterialDescription", "").strip():
            return f"Anvelopa {i}: lipsește descrierea (dimensiune / model)."
        if parse_mm(t.get("TreadDepth", "")) is None:
            return f"Anvelopa {i}: profilul trebuie să fie o valoare în mm (ex: 6 sau 5,5)."
    return None


def archive(rows_df, reason):
    if rows_df is None or not len(rows_df):
        return []
    df = ensure_schema(rows_df.drop(columns=["_plate"], errors="ignore"), GY_COLS)[GY_COLS]
    return [[now_s(), reason] + r for r in df.values.tolist()]


def describe(rows_df):
    if rows_df is None or not len(rows_df):
        return "(nimic)"
    parts = []
    for _, r in rows_df.iterrows():
        parts.append(f"{r['BRAND']} {r['MaterialDescription']} [{SEASON_RO.get(r['ProductGroup'], r['ProductGroup'])}] "
                     f"{r['TreadDepth']}mm DOT {r['DOT']}")
    return f"{len(rows_df)} anv.: " + "; ".join(parts)


# ---------------------------------------------------------------------------
# Operațiuni
# ---------------------------------------------------------------------------
def do_swap(plate, tyres, assign_code="", user_note=""):
    hotel, ty = load(HOTEL, fresh=True), load(TY, fresh=True)
    i = find_row(hotel, plate, only_status=ST_DEP)
    if i is None:
        raise BackendError(f"Nu găsesc niciun set DEPOZITAT pentru {plate}.")
    err = validate_tyres(tyres)
    if err:
        raise BackendError(err)
    h = hotel.loc[i]
    code = h["PositionCode"] or assign_code
    if not h["PositionCode"] and assign_code and assign_code in occupied_map(hotel):
        raise BackendError(f"Poziția {assign_code} este ocupată de {occupied_map(hotel)[assign_code]}.")
    old = tyres_of(ty, plate)
    legacy = old["ServiceProviderStorageLocation"].iloc[0] if len(old) else ""
    new = make_tyre_rows(vehicle_template(ty, plate, h), tyres, legacy)
    ty = pd.concat([ty[ty["_plate"] != norm_plate(plate)], new], ignore_index=True)
    hotel.at[i, "PositionCode"] = code
    hotel.at[i, "StorageDate"] = today_s()
    hotel.at[i, "Season"] = "/".join(uniq(new["ProductGroup"]))
    worn = [t for t in tyres if is_worn(t["TreadDepth"])]
    det = f"Montat pe mașină: {describe(old)} || Pus pe raft: {describe(new)}"
    if worn:
        det += f" || ⚠️ RECOMANDARE ANVELOPE NOI: {len(worn)} anv. sub {CFG['worn_mm']:g} mm"
    save(hotel=hotel, ty=ty, archive_rows=archive(old, f"SCHIMB {today_s()}: scos de pe raft și montat pe mașină"),
         logs=[log_row("SCHIMB", hotel.at[i, "RegistrationNumber"], det, code, user_note)])
    return code, len(worn)


def do_reception(meta, tyres, code, user_note=""):
    hotel, ty = load(HOTEL, fresh=True), load(TY, fresh=True)
    plate = norm_plate(meta["RegistrationNumber"])
    if find_row(hotel, plate, only_status=ST_DEP) is not None:
        raise BackendError(f"Mașina {plate} are deja un set DEPOZITAT. Folosește tab-ul Schimb sezon.")
    if code and code in occupied_map(hotel):
        raise BackendError(f"Poziția {code} tocmai a fost ocupată de {occupied_map(hotel)[code]}. Alege alta.")
    err = validate_tyres(tyres)
    if err:
        raise BackendError(err)
    tpl = vehicle_template(ty, "__nou__")
    tpl.update({k: meta.get(k, "") for k in ("SOLD-TO", "FleetName", "CITY", "Fleet VIN", "Chassis Num", "Make/Model")})
    tpl["RegistrationNumber"] = plate
    new = make_tyre_rows(tpl, tyres)
    ty = pd.concat([ty[ty["_plate"] != plate], new], ignore_index=True)
    rec = {c: "" for c in HOTEL_COLS}
    rec.update({"RegistrationNumber": plate, "FleetName": meta.get("FleetName", ""), "PositionCode": code,
                "Status": ST_DEP, "StorageDate": today_s(), "Season": "/".join(uniq(new["ProductGroup"])),
                "Phone": meta.get("Phone", ""), "Email": meta.get("Email", ""),
                "VIN": norm_vin(meta.get("Chassis Num", "")) or norm_vin(meta.get("Fleet VIN", ""))})
    j = find_row(hotel, plate)
    if j is not None:  # client vechi, RIDICAT -> refolosim rândul
        for k, v in rec.items():
            if k in CAR_PEOPLE + ["VIN"] and not v:
                continue  # păstrăm utilizatorul / VIN-ul deja salvate
            hotel.at[j, k] = v
    else:
        hotel = pd.concat([hotel, pd.DataFrame([rec])], ignore_index=True)
    det = f"Recepție: {describe(new)}"
    if any(is_worn(t["TreadDepth"]) for t in tyres):
        det += f" || ⚠️ RECOMANDARE ANVELOPE NOI (sub {CFG['worn_mm']:g} mm)"
    save(hotel=hotel, ty=ty, logs=[log_row("RECEPTIE", plate, det, code, user_note)])


def do_exit(plate, note=""):
    hotel, ty = load(HOTEL, fresh=True), load(TY, fresh=True)
    i = find_row(hotel, plate, only_status=ST_DEP)
    if i is None:
        raise BackendError(f"Nu găsesc niciun set DEPOZITAT pentru {plate}.")
    code = hotel.at[i, "PositionCode"]
    old = tyres_of(ty, plate)
    hotel.at[i, "Status"] = ST_RID
    hotel.at[i, "ExitDate"] = today_s()
    ty = ty[ty["_plate"] != norm_plate(plate)]
    save(hotel=hotel, ty=ty, archive_rows=archive(old, f"IESIRE {today_s()}: ridicat definitiv"),
         logs=[log_row("IESIRE", hotel.at[i, "RegistrationNumber"],
                       f"Set ridicat definitiv: {describe(old)}. Poziția {code or '-'} a fost eliberată.", code, note)])
    return code


def do_generate_positions(r_from, r_to, levels, legs, fleet, update_existing):
    pos = load(POZ, fresh=True)
    existing = set(pos["PositionCode"])
    added = updated = 0
    new_rows = []
    for r in range(r_from, r_to + 1):
        for n in range(1, levels + 1):
            for p in range(1, legs + 1):
                code = f"R{r}-N{n}-P{p}"
                if code in existing:
                    if update_existing:
                        pos.loc[pos["PositionCode"] == code, "FleetName"] = fleet
                        updated += 1
                else:
                    new_rows.append([code, str(r), str(n), str(p), fleet, ""])
                    added += 1
    if new_rows:
        pos = pd.concat([pos, pd.DataFrame(new_rows, columns=POZ_COLS)], ignore_index=True)
    backend().write(POZ, sync_positions(load(HOTEL, fresh=True), sort_positions(pos)))
    clear_cache()
    return added, updated


def do_assign_rows(rows, fleet):
    pos = load(POZ, fresh=True)
    mask = pos["Row"].isin([str(r) for r in rows])
    pos.loc[mask, "FleetName"] = fleet
    backend().write(POZ, pos)
    clear_cache()
    return int(mask.sum())


def do_delete_free_in_row(row):
    pos = load(POZ, fresh=True)
    occ = occupied_map(load(HOTEL, fresh=True))
    mask = (pos["Row"] == str(row)) & (~pos["PositionCode"].isin(occ.keys()))
    backend().write(POZ, pos[~mask])
    clear_cache()
    return int(mask.sum())


# ---------------------------------------------------------------------------
# Recepții leasing + fișe GY
# ---------------------------------------------------------------------------
def new_id(prefix, plate=""):
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]}-{norm_plate(plate)}"


def rec_age(rec_row):
    d = parse_date(rec_row.get("ReceptionDate", ""))
    return (pd.Timestamp(date.today()) - d).days if pd.notna(d) else None


def open_receptions(rec, plate=None, vin=""):
    o = rec[rec["Status"].str.strip().str.upper() == RC_OPEN]
    if plate is not None or vin:
        p, v = norm_plate(plate or ""), norm_vin(vin)
        m = pd.Series(False, index=o.index)
        if p:
            m |= o["RegistrationNumber"].map(norm_plate) == p
        if v:
            m |= o["VIN"].map(norm_vin) == v
        o = o[m]
    return o


def rec_tyres(rty, rec_id):
    t = rty[rty["ReceptionId"] == rec_id].copy()
    t["_n"] = t["TyreNo"].map(int_key)
    return t.sort_values("_n").drop(columns="_n")


def describe_rtyres(t):
    if t is None or not len(t):
        return "(nimic)"
    return f"{len(t)} anv.: " + "; ".join(
        f"{r['BRAND']} {r['TyreModel']} {r['MaterialDescription']} [{SEASON_RO.get(r['ProductGroup'], r['ProductGroup'])}]"
        f" {r['TreadDepth']}mm DOT {r['DOT']}" + (f" ({r['Axle']})" if r["Axle"] else "")
        for _, r in t.iterrows())


def clean_rtyres(tyres):
    """Listă de dicturi (din editor sau import) -> anvelope curate; rândurile complet goale sunt ignorate."""
    out = []
    for t in tyres:
        t = {k: ("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()) for k, v in t.items()}
        if not any(t.get(k, "") for k in ("MaterialDescription", "BRAND", "TyreModel", "DOT", "TreadDepth", "Note")):
            continue
        out.append({
            "MaterialDescription": t.get("MaterialDescription", "").upper(), "BRAND": t.get("BRAND", "").upper(),
            "TyreModel": t.get("TyreModel", "").upper(), "ProductGroup": norm_season(t.get("ProductGroup", "")),
            "DOT": t.get("DOT", ""), "TreadDepth": fmt_mm(t["TreadDepth"]) if t.get("TreadDepth", "") else "",
            "Axle": t.get("Axle", "").upper(), "Note": t.get("Note", ""),
        })
    return out


def validate_rtyres(tyres):
    if not tyres:
        return "Adaugă cel puțin o anvelopă."
    for i, t in enumerate(tyres, 1):
        if not t["MaterialDescription"]:
            return f"Anvelopa {i}: lipsește dimensiunea."
        if t["TreadDepth"] and parse_mm(t["TreadDepth"]) is None:
            return f"Anvelopa {i}: profilul trebuie să fie în mm (ex: 7 sau 6,5)."
    return None


def _rty_rows(rec_id, plate, tyres):
    return [[rec_id, str(k), plate] + [t[c] for c in RTY_COLS[3:]] for k, t in enumerate(tyres, 1)]


def update_car_people(plate, people):
    """Actualizează utilizatorul / firma client pe fișa mașinii din 'Hotel' (doar valorile completate)."""
    people = {k: str(v).strip() for k, v in people.items() if k in CAR_PEOPLE + ["VIN"]}
    hotel = load(HOTEL, fresh=True)
    j = find_row(hotel, plate)
    if j is None or not any(people.values()):
        return False
    changed = False
    for k, v in people.items():
        if k == "VIN":
            v = norm_vin(v)
            if not v or hotel.at[j, k]:
                continue
        if v and hotel.at[j, k] != v:
            hotel.at[j, k] = v
            changed = True
    if changed:
        backend().write(HOTEL, ensure_schema(hotel, HOTEL_COLS))
        clear_cache()
    return changed


def do_leasing_reception(meta, tyres, allow_duplicate=False, source="", log=True):
    """O recepție = un set trimis de leasing pentru o mașină. Întoarce ReceptionId."""
    plate = norm_plate(meta.get("RegistrationNumber", ""))
    vin = norm_vin(meta.get("VIN", ""))
    if str(meta.get("VIN", "")).strip() and not vin:
        raise BackendError("VIN-ul trebuie să aibă cel puțin 6 caractere.")
    if not plate and not vin:
        raise BackendError("Completează numărul auto sau VIN-ul.")
    tyres = clean_rtyres(tyres)
    err = validate_rtyres(tyres)
    if err:
        raise BackendError(err)
    rec = load(REC, fresh=True)
    if len(open_receptions(rec, plate or None, vin)) and not allow_duplicate:
        raise BackendError(f"Mașina {plate or 'VIN ' + vin} are deja o recepție deschisă (RECEPTIONAT). Bifează "
                           "confirmarea dacă este într-adevăr un set nou.")
    rid = new_id("RC", plate or vin[-6:])
    rdate = meta.get("ReceptionDate") or today_s()
    row = {c: "" for c in REC_COLS}
    row.update({"ReceptionId": rid, "RegistrationNumber": plate, "FleetName": meta.get("FleetName", "").strip(),
                "ReceptionDate": str(rdate), "Tyres": str(len(tyres)),
                "Season": "/".join(uniq(t["ProductGroup"] for t in tyres)),
                "WaitingLocation": meta.get("WaitingLocation", "").strip(), "Note": meta.get("Note", "").strip(),
                "Status": RC_OPEN, "CreatedAt": now_s(), "Operator": st.session_state.get("operator", "")})
    for k in CAR_PEOPLE:
        row[k] = str(meta.get(k, "")).strip()
    row["VIN"] = vin
    row["Condition"] = rimp.norm_condition(meta.get("Condition", ""), "NOI")
    be = backend()
    be.append_many(RTY, _rty_rows(rid, plate, tyres), RTY_COLS)
    be.append_many(REC, [[row[c] for c in REC_COLS]], REC_COLS)
    if log:
        be.append_many(IST, [log_row("RECEPTIE_LEASING", plate or f"VIN {vin}",
                                     f"Recepție leasing {rid} ({row['FleetName'] or '-'}, {row['Condition']}"
                                     + (f", VIN {vin}" if vin else "") + f"): {describe_rtyres(pd.DataFrame(tyres))}"
                                     + (f" · {source}" if source else ""), "", row["Note"])], IST_COLS)
    if plate:
        update_car_people(plate, row)
    clear_cache()
    return rid


def do_bulk_leasing_reception(recs, rdate, waiting_loc="", skip_open=True, source=""):
    """Recepții din import (o recepție pe număr auto). Întoarce (create, sărite)."""
    rec = load(REC, fresh=True)
    orc = open_receptions(rec)
    open_pl = set(orc["RegistrationNumber"].map(norm_plate)) - {""}
    open_vin = set(orc["VIN"].map(norm_vin)) - {""}
    rec_rows, rty_rows, logs, created, skipped = [], [], [], [], []
    op = st.session_state.get("operator", "")
    for r in recs:
        plate = norm_plate(r["RegistrationNumber"])
        vin = norm_vin(r.get("VIN", ""))
        tyres = clean_rtyres(r["tyres"])
        if (not plate and not vin) or validate_rtyres(tyres) or (
                skip_open and ((plate and plate in open_pl) or (vin and vin in open_vin))):
            skipped.append(plate or (f"VIN {vin}" if vin else "(fără număr)"))
            continue
        rid = new_id("RC", plate or vin[-6:])
        row = {c: "" for c in REC_COLS}
        row.update({"ReceptionId": rid, "RegistrationNumber": plate, "FleetName": r.get("FleetName", ""),
                    "ReceptionDate": str(rdate), "Tyres": str(len(tyres)),
                    "Season": "/".join(uniq(t["ProductGroup"] for t in tyres)), "WaitingLocation": waiting_loc,
                    "Status": RC_OPEN, "CreatedAt": now_s(), "Operator": op})
        for k in CAR_PEOPLE:
            row[k] = str(r.get(k, "")).strip()
        row["VIN"] = vin
        row["Condition"] = rimp.norm_condition(r.get("Condition", ""), "NOI")
        rec_rows.append([row[c] for c in REC_COLS])
        rty_rows += _rty_rows(rid, plate, tyres)
        logs.append(log_row("RECEPTIE_LEASING", plate or f"VIN {vin}", f"Recepție leasing {rid} (import{(': ' + source) if source else ''}): "
                            f"{describe_rtyres(pd.DataFrame(tyres))}"))
        created.append(plate or f"VIN {vin}")
        open_pl.add(plate)
        open_vin.add(vin)
    be = backend()
    be.append_many(RTY, rty_rows, RTY_COLS)
    be.append_many(REC, rec_rows, REC_COLS)
    be.append_many(IST, logs, IST_COLS)
    for r in rec_rows:
        d = dict(zip(REC_COLS, r))
        if d["RegistrationNumber"] and (any(d[k] for k in CAR_PEOPLE) or d["VIN"]):
            update_car_people(d["RegistrationNumber"], d)
    clear_cache()
    return created, skipped


def do_edit_reception(rec_id, header, tyres):
    """Salvează modificările unei recepții (antet + fiecare anvelopă) și scrie diferențele în Istoric."""
    rec, rty = load(REC, fresh=True), load(RTY, fresh=True)
    idx = rec.index[rec["ReceptionId"] == rec_id].tolist()
    if not idx:
        raise BackendError("Recepția nu mai există.")
    j = idx[0]
    plate = rec.at[j, "RegistrationNumber"]
    tyres = clean_rtyres(tyres)
    err = validate_rtyres(tyres)
    if err:
        raise BackendError(err)
    changes = []
    for k in ("FleetName", "ReceptionDate", "WaitingLocation", "Note", "VIN", "Condition") + tuple(CAR_PEOPLE):
        if k in header:
            v = str(header[k]).strip()
            if k == "VIN":
                v = norm_vin(v)
                if str(header[k]).strip() and not v:
                    raise BackendError("VIN-ul trebuie să aibă cel puțin 6 caractere.")
            if k == "Condition":
                v = rimp.norm_condition(v, rec.at[j, k] or "NOI")
            if rec.at[j, k] != v:
                changes.append(f"{DISPLAY.get(k, k)}: '{rec.at[j, k]}' → '{v}'")
                rec.at[j, k] = v
    old = rec_tyres(rty, rec_id)
    old_l = [{c: r[c] for c in RTY_COLS[3:]} for _, r in old.iterrows()]
    for n in range(max(len(old_l), len(tyres))):
        a = old_l[n] if n < len(old_l) else None
        b = tyres[n] if n < len(tyres) else None
        if a is None:
            changes.append(f"Anv. {n + 1} adăugată: {b['BRAND']} {b['MaterialDescription']} {b['TreadDepth']}mm DOT {b['DOT']}")
        elif b is None:
            changes.append(f"Anv. {n + 1} ștearsă: {a['BRAND']} {a['MaterialDescription']}")
        else:
            diff = [f"{DISPLAY.get(c, c)} '{a[c]}'→'{b[c]}'" for c in RTY_COLS[3:] if a[c] != b[c]]
            if diff:
                changes.append(f"Anv. {n + 1}: " + ", ".join(diff))
    if not changes:
        return 0
    rec.at[j, "Tyres"] = str(len(tyres))
    rec.at[j, "Season"] = "/".join(uniq(t["ProductGroup"] for t in tyres))
    rty = pd.concat([rty[rty["ReceptionId"] != rec_id],
                     pd.DataFrame(_rty_rows(rec_id, plate, tyres), columns=RTY_COLS)], ignore_index=True)
    be = backend()
    be.write(RTY, ensure_schema(rty, RTY_COLS)[RTY_COLS])
    be.write(REC, ensure_schema(rec, REC_COLS))
    be.append_many(IST, [log_row("EDITARE_RECEPTIE", plate or rec.at[j, "VIN"], f"{rec_id}: " + " | ".join(changes))], IST_COLS)
    if plate:
        update_car_people(plate, {k: rec.at[j, k] for k in CAR_PEOPLE + ["VIN"]})
    clear_cache()
    return len(changes)


def _new_fisa(rec_row, ftype, note=""):
    r = {c: "" for c in FISE_COLS}
    r.update({"FisaId": new_id("FG", rec_row["RegistrationNumber"]), "ReceptionId": rec_row.get("ReceptionId", ""),
              "RegistrationNumber": rec_row["RegistrationNumber"], "FleetName": rec_row.get("FleetName", ""),
              "Type": ftype, "Status": F_TODO, "CreatedDate": today_s(),
              "Note": " | ".join(x for x in ([f"VIN {rec_row.get('VIN', '')}"] if rec_row.get("VIN", "") else []) + [note] if x),
              "Operator": st.session_state.get("operator", "")})
    return [r[c] for c in FISE_COLS]


def do_leasing_swap(rec_id, tyres, assign_code="", user_note="", replace_existing=False):
    """Setul recepționat se montează; anvelopele date jos intră pe raft (DEPOZITAT) + fișă GY de introdus."""
    rec, rty = load(REC, fresh=True), load(RTY, fresh=True)
    idx = rec.index[rec["ReceptionId"] == rec_id].tolist()
    if not idx or rec.at[idx[0], "Status"].strip().upper() != RC_OPEN:
        raise BackendError("Recepția nu mai este deschisă (poate a fost deja montată).")
    j = idx[0]
    r = rec.loc[j]
    plate = norm_plate(r["RegistrationNumber"])
    if not plate:
        raise BackendError("Recepția are doar VIN. Leag-o întâi de numărul auto al mașinii.")
    err = validate_tyres(tyres)
    if err:
        raise BackendError(err)
    hotel, ty = load(HOTEL, fresh=True), load(TY, fresh=True)
    i = find_row(hotel, plate, only_status=ST_DEP)
    old = tyres_of(ty, plate)
    occ = occupied_map(hotel)
    if i is not None:
        if not replace_existing:
            raise BackendError(f"Mașina {plate} are deja un set DEPOZITAT pe raft. Bifează confirmarea că setul dat "
                               "jos îl înlocuiește în evidență.")
        code = hotel.at[i, "PositionCode"] or assign_code
    else:
        code = assign_code
    if code and code in occ and norm_plate(occ[code]) != plate:
        raise BackendError(f"Poziția {code} este ocupată de {occ[code]}.")
    hrow = {"FleetName": r["FleetName"]} if i is None else hotel.loc[i]
    tpl = vehicle_template(ty, plate, hrow)
    if not tpl.get("FleetName"):
        tpl["FleetName"] = r["FleetName"]
    legacy = old["ServiceProviderStorageLocation"].iloc[0] if len(old) else ""
    new = make_tyre_rows(tpl, tyres, legacy)
    ty = pd.concat([ty[ty["_plate"] != plate], new], ignore_index=True)
    vals = {"PositionCode": code, "Status": ST_DEP, "StorageDate": today_s(), "ExitDate": "",
            "Season": "/".join(uniq(new["ProductGroup"]))}
    if i is None:
        k = find_row(hotel, plate)
        if k is None:
            base = {c: "" for c in HOTEL_COLS}
            base.update({"RegistrationNumber": plate, "FleetName": r["FleetName"]})
            hotel = pd.concat([hotel, pd.DataFrame([base])], ignore_index=True)
            k = hotel.index[-1]
        i = k
    for c, v in vals.items():
        hotel.at[i, c] = v
    for c in CAR_PEOPLE:
        if r.get(c, ""):
            hotel.at[i, c] = r[c]
    if not hotel.at[i, "VIN"]:
        hotel.at[i, "VIN"] = norm_vin(r.get("VIN", "")) or (car_vins(plate, hotel, ty) or [""])[0]
    if not hotel.at[i, "FleetName"]:
        hotel.at[i, "FleetName"] = r["FleetName"]
    mounted = rec_tyres(rty, rec_id)
    det = f"Montat setul recepționat {rec_id}: {describe_rtyres(mounted)} || Pus pe raft: {describe(new)}"
    if len(old):
        det += f" || Set vechi din evidență înlocuit: {describe(old)}"
    worn = [t for t in tyres if is_worn(t["TreadDepth"])]
    if worn:
        det += f" || ⚠️ RECOMANDARE ANVELOPE NOI: {len(worn)} anv. sub {CFG['worn_mm']:g} mm"
    save(hotel=hotel, ty=ty,
         archive_rows=archive(old, f"SCHIMB LEASING {today_s()}: set vechi înlocuit în evidență") if len(old) else None,
         logs=[log_row("SCHIMB_LEASING", plate, det, code, user_note)])
    rec.at[j, "Status"] = RC_SWAP
    rec.at[j, "SwapDate"] = today_s()
    be = backend()
    be.write(REC, ensure_schema(rec, REC_COLS))
    be.append_many(FISE, [_new_fisa(rec.loc[j], FT_SWAP)], FISE_COLS)
    clear_cache()
    return code, len(worn)


def do_myway(rec_ids, note=""):
    """Seturi nemontate la sfârșit de sezon: introduse în My Way -> EXTRA_DEPOZITARE + fișă GY de introdus."""
    rec = load(REC, fresh=True)
    fise, logs, n = [], [], 0
    for rid in rec_ids:
        idx = rec.index[(rec["ReceptionId"] == rid) & (rec["Status"].str.upper() == RC_OPEN)].tolist()
        if not idx:
            continue
        j = idx[0]
        rec.at[j, "Status"] = RC_EXTRA
        rec.at[j, "MyWayDate"] = today_s()
        fise.append(_new_fisa(rec.loc[j], FT_EXTRA, note))
        logs.append(log_row("MY_WAY", rec.at[j, "RegistrationNumber"] or f"VIN {rec.at[j, 'VIN']}",
                            f"Recepția {rid} (din {rec.at[j, 'ReceptionDate']}) introdusă în My Way – EXTRA DEPOZITARE",
                            "", note))
        n += 1
    if n:
        be = backend()
        be.write(REC, ensure_schema(rec, REC_COLS))
        be.append_many(FISE, fise, FISE_COLS)
        be.append_many(IST, logs, IST_COLS)
        clear_cache()
    return n


def do_fisa_status(fisa_ids, new_status, on_date=None, gy_ref="", note=""):
    """Avansează statusul fișelor GY (doar tranzițiile permise). Întoarce (actualizate, sărite)."""
    fise = load(FISE, fresh=True)
    d = str(on_date or today_s())
    done, skipped, logs = 0, 0, []
    for fid in fisa_ids:
        idx = fise.index[fise["FisaId"] == fid].tolist()
        if not idx:
            skipped += 1
            continue
        j = idx[0]
        cur = fise.at[j, "Status"].strip().upper() or F_TODO
        if new_status not in F_NEXT.get(cur, []):
            skipped += 1
            continue
        fise.at[j, "Status"] = new_status
        if F_DATE.get(new_status):
            fise.at[j, F_DATE[new_status]] = d
        if gy_ref:
            fise.at[j, "GYRef"] = gy_ref
        if note:
            fise.at[j, "Note"] = (fise.at[j, "Note"] + " | " if fise.at[j, "Note"] else "") + f"{d}: {note}"
        logs.append(log_row("FISA_GY", fise.at[j, "RegistrationNumber"],
                            f"Fișa {fid} ({fise.at[j, 'Type']}): {cur} → {new_status}"
                            + (f" · nr. GY {gy_ref}" if gy_ref else ""), "", note))
        done += 1
    if done:
        be = backend()
        be.write(FISE, ensure_schema(fise, FISE_COLS))
        be.append_many(IST, logs, IST_COLS)
        clear_cache()
    return done, skipped


def do_edit_car_people(plate, people):
    hotel = load(HOTEL, fresh=True)
    j = find_row(hotel, plate)
    if j is None:
        raise BackendError(f"Mașina {plate} nu are fișă în hotel.")
    ch = []
    for k in CAR_PEOPLE + ["VIN"]:
        if k not in people:
            continue
        v = str(people.get(k, "")).strip()
        if k == "VIN":
            v = norm_vin(v)
            if str(people[k]).strip() and not v:
                raise BackendError("VIN-ul trebuie să aibă cel puțin 6 caractere.")
        if hotel.at[j, k] != v:
            ch.append(f"{DISPLAY.get(k, k)}: '{hotel.at[j, k]}' → '{v}'")
            hotel.at[j, k] = v
    if ch:
        backend().write(HOTEL, ensure_schema(hotel, HOTEL_COLS))
        backend().append_many(IST, [log_row("EDITARE_MASINA", hotel.at[j, "RegistrationNumber"], " | ".join(ch))], IST_COLS)
        clear_cache()
    return len(ch)


# --- VIN: legătura mașină <-> recepție -------------------------------------------
norm_vin = rimp.norm_vin


def vin_match(q, vin):
    """VIN complet sau ultimele 6+ caractere."""
    q, vin = norm_vin(q), norm_vin(vin)
    return bool(q and vin and (vin == q or vin.endswith(q)))


def car_vins(plate, hotel=None, ty=None):
    hotel = load(HOTEL) if hotel is None else hotel
    ty = load(TY) if ty is None else ty
    p = norm_plate(plate)
    out = []
    if p:
        out += [norm_vin(v) for v in hotel.loc[hotel["RegistrationNumber"].map(norm_plate) == p, "VIN"]]
        t = ty[ty["_plate"] == p] if "_plate" in ty else ty.iloc[0:0]
        out += [norm_vin(v) for c in ("Chassis Num", "Fleet VIN") for v in t[c]]
    return uniq(v for v in out if v)


def receptions_for(rec, plate="", vins=(), only_open=False):
    p = norm_plate(plate)
    vins = [v for v in vins if v]
    m = pd.Series(False, index=rec.index)
    if p:
        m |= rec["RegistrationNumber"].map(norm_plate) == p
    for v in vins:
        m |= rec["VIN"].map(lambda x: bool(norm_vin(x)) and norm_vin(x) == v).astype(bool)
    if only_open:
        m &= rec["Status"].str.strip().str.upper() == RC_OPEN
    return rec[m]


def resolve_car(query, hotel=None, ty=None, rec=None):
    """Număr auto SAU VIN (complet / ultimele 6+). Întoarce {"plates": [...], "vins": [...], "by": "plate"|"vin"|""}."""
    hotel = load(HOTEL) if hotel is None else hotel
    ty = load(TY) if ty is None else ty
    rec = load(REC) if rec is None else rec
    p = norm_plate(query)
    if not p:
        return {"plates": [], "vins": [], "by": ""}
    known = set(hotel["RegistrationNumber"].map(norm_plate)) | set(ty["_plate"]) | set(rec["RegistrationNumber"].map(norm_plate))
    if p in known:
        return {"plates": [p], "vins": car_vins(p, hotel, ty), "by": "plate"}
    plates, vins = [], []
    if len(p) >= 6:
        for _, r in hotel.iterrows():
            if vin_match(p, r["VIN"]):
                plates.append(norm_plate(r["RegistrationNumber"]))
                vins.append(norm_vin(r["VIN"]))
        for c in ("Chassis Num", "Fleet VIN"):
            mm = ty[ty[c].map(lambda v: vin_match(p, v)).astype(bool)]
            plates += list(mm["_plate"])
            vins += [norm_vin(v) for v in mm[c]]
        for _, r in rec.iterrows():
            if vin_match(p, r["VIN"]):
                vins.append(norm_vin(r["VIN"]))
                if norm_plate(r["RegistrationNumber"]):
                    plates.append(norm_plate(r["RegistrationNumber"]))
    plates = uniq(x for x in plates if x)
    vins = uniq(x for x in vins if x)
    for pl in plates:
        vins = uniq(vins + car_vins(pl, hotel, ty))
    return {"plates": plates, "vins": vins, "by": "vin" if (plates or vins) else ""}


def do_link_reception(rec_id, plate):
    """Leagă o recepție venită doar cu VIN de un număr auto."""
    plate = norm_plate(plate)
    if not plate:
        raise BackendError("Completează numărul auto.")
    rec, rty = load(REC, fresh=True), load(RTY, fresh=True)
    idx = rec.index[rec["ReceptionId"] == rec_id].tolist()
    if not idx:
        raise BackendError("Recepția nu mai există.")
    j = idx[0]
    old = rec.at[j, "RegistrationNumber"]
    rec.at[j, "RegistrationNumber"] = plate
    rty.loc[rty["ReceptionId"] == rec_id, "RegistrationNumber"] = plate
    be = backend()
    be.write(REC, ensure_schema(rec, REC_COLS))
    be.write(RTY, ensure_schema(rty, RTY_COLS)[RTY_COLS])
    be.append_many(IST, [log_row("LEGARE_RECEPTIE", plate, f"Recepția {rec_id} (VIN {rec.at[j, 'VIN'] or '-'}) legată de "
                                 f"numărul {plate}" + (f" (înainte: {old})" if old else ""))], IST_COLS)
    update_car_people(plate, {k: rec.at[j, k] for k in CAR_PEOPLE + ["VIN"]})
    clear_cache()
    return plate


def all_fleets(*dfs):
    s = set(DEFAULT_FLEETS)
    for d in dfs:
        if d is not None and "FleetName" in d:
            s |= {f.strip() for f in d["FleetName"] if f.strip() and f.strip().upper() != COMUN}
    return sorted(s, key=str.upper)


def fleets_with_rows(pos):
    return sorted({x.strip() for x in pos["FleetName"] if x.strip() and x.strip().upper() != COMUN})


def free_positions_ordered(pos, hotel, fleet=""):
    """Poziții libere: întâi rândurile flotei, apoi cele COMUNE, apoi restul."""
    occ = occupied_map(hotel)
    free = sort_positions(pos[~pos["PositionCode"].isin(occ.keys())])
    fl = fleet.strip().upper()
    fu = free["FleetName"].str.strip().str.upper()
    own = free[fu == fl] if fl else free.iloc[0:0]
    comun = free[fu.isin([COMUN, ""])]
    other = free[~free.index.isin(own.index) & ~free.index.isin(comun.index)]
    return pd.concat([own, comun, other])


# ---------------------------------------------------------------------------
# GY Fleet – import / export (21 coloane, CITY de două ori)
# ---------------------------------------------------------------------------
def _hkey(h):
    return re.sub(r"[^a-z0-9]", "", str(h).lower())


GY_ALIASES = {_hkey(c): c for c in GY_COLS}
GY_ALIASES.update({_hkey(k): v for k, v in {
    "CITY.1": "CITY_2", "Registration Number": "RegistrationNumber", "Plate": "RegistrationNumber",
    "Numar auto": "RegistrationNumber", "Nr auto": "RegistrationNumber", "Fleet Name": "FleetName",
    "Chassis Number": "Chassis Num", "VIN": "Chassis Num", "Make Model": "Make/Model",
    "Material Description": "MaterialDescription", "Storage Date": "StorageDate", "Tread Depth": "TreadDepth",
    "StorageNote": NOTE, "Storage Note": NOTE, "Comments": NOTE, "Product Group": "ProductGroup",
    "Wheel Type": "WheelType", "Storage Location": "ServiceProviderStorageLocation",
}.items()})


def _clean_cell(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, (datetime, pd.Timestamp, date)):
        return us_date(pd.Timestamp(v))
    s = str(v).strip()
    if s.lower() in ("nan", "nat", "none"):
        return ""
    if re.fullmatch(r"\d+\.0", s):  # numere citite ca float din Excel (ex. DOT 2324.0)
        s = s[:-2]
    return s


def _us(s):
    d = parse_date(s)
    return us_date(d) if pd.notna(d) and s else s


def read_gy_file(name, data):
    """Citește un export GY Fleet (.xlsx/.csv), păstrând ambele coloane CITY. Întoarce (df, coloane_ignorate)."""
    low = name.lower()
    if low.endswith((".xlsx", ".xlsm", ".xls")):
        try:
            raw = pd.read_excel(io.BytesIO(data), dtype=object, header=None)
        except Exception as e:  # noqa: BLE001
            raise BackendError(f"Nu pot citi fișierul Excel: {e}")
    else:
        text = None
        for enc in ("utf-8-sig", "cp1250", "latin-1"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise BackendError("Nu pot citi fișierul CSV (codare necunoscută).")
        first = text.splitlines()[0] if text else ""
        delim = max([",", ";", "\t"], key=first.count)
        rows = list(csv.reader(io.StringIO(text), delimiter=delim))
        w = max((len(r) for r in rows), default=0)
        raw = pd.DataFrame([r + [""] * (w - len(r)) for r in rows])
    vals = [[_clean_cell(v) for v in row] for row in raw.values.tolist()]
    df = values_to_df(vals)
    mapping, unknown = {}, []
    for c in df.columns:
        target = GY_ALIASES.get(_hkey(c))
        if target and target not in mapping.values():
            mapping[c] = target
        elif not str(c).startswith("Coloana_"):
            unknown.append(str(c))
    if "RegistrationNumber" not in mapping.values():
        raise BackendError("Fișierul nu are coloana RegistrationNumber (număr auto). "
                           f"Coloane găsite: {', '.join(map(str, df.columns))}")
    df = ensure_schema(df[list(mapping)].rename(columns=mapping), GY_COLS)[GY_COLS]
    df["StorageDate"] = df["StorageDate"].map(_us)
    df["TreadDepth"] = df["TreadDepth"].map(lambda s: fmt_mm(s) if s else s)
    df, skipped = clean_gy(df)
    return df, unknown, skipped


def _set_key(rows):
    def k(r):
        vals = []
        for c in GY_COLS:
            v = str(r[c]).strip()
            if c == "StorageDate":
                d = parse_date(v)
                v = d.strftime("%Y-%m-%d") if pd.notna(d) else v
            elif c == "TreadDepth":
                m = parse_mm(v)
                v = f"{m:.1f}" if m is not None else v
            elif c == "ProductGroup":
                v = norm_season(v)
            vals.append(v)
        return tuple(vals)
    return sorted(k(r) for _, r in rows.iterrows())


def plan_gy_import(hotel, ty, imp):
    """Compară importul (pe mașini) cu datele aplicației. Nu scrie nimic."""
    new, changed, unchanged, ridicat = [], [], 0, []
    groups = {k: g for k, g in ty.groupby("_plate")} if len(ty) else {}
    for plate, g in imp.groupby("RegistrationNumber", sort=False):
        i = find_row(hotel, plate)
        if i is None:
            new.append(plate)
        elif hotel.at[i, "Status"] != ST_DEP:
            ridicat.append(plate)
        elif _set_key(g) != _set_key(groups.get(plate, ty.iloc[0:0])):
            changed.append(plate)
        else:
            unchanged += 1
    return {"new": new, "changed": changed, "unchanged": unchanged, "ridicat": ridicat}


def do_gy_import(imp, apply_changes=False, source=""):
    hotel, ty = load(HOTEL, fresh=True), load(TY, fresh=True)
    plan = plan_gy_import(hotel, ty, imp)
    todo = plan["new"] + (plan["changed"] if apply_changes else [])
    if not todo:
        return plan, 0
    sel = imp[imp["RegistrationNumber"].isin(todo)]
    old = ty[ty["_plate"].isin(todo)]
    ty = pd.concat([ty[~ty["_plate"].isin(todo)], sel], ignore_index=True)
    logs = []
    newh = hotel_from_tyres(sel[sel["RegistrationNumber"].isin(plan["new"])])
    for plate in plan["new"]:
        logs.append(log_row("IMPORT", plate, f"Mașină nouă din GY Fleet (fără poziție): "
                            f"{describe(sel[sel['RegistrationNumber'] == plate])}", "", source))
    if apply_changes:
        for plate in plan["changed"]:
            i = find_row(hotel, plate)
            g = sel[sel["RegistrationNumber"] == plate]
            hotel.at[i, "Season"] = "/".join(uniq(g["ProductGroup"]))
            logs.append(log_row("IMPORT", plate, f"Anvelope înlocuite din GY Fleet. Înainte: "
                                f"{describe(old[old['_plate'] == plate])} || Acum: {describe(g)}",
                                hotel.at[i, "PositionCode"], source))
    hotel = pd.concat([hotel, newh], ignore_index=True)
    save(hotel=hotel, ty=ty, archive_rows=archive(old, f"IMPORT {today_s()}: înlocuit din GY Fleet ({source})"),
         logs=logs)
    return plan, len(todo)


def gy_export_values(ty):
    df = ensure_schema(ty.drop(columns=["_plate"], errors="ignore"), GY_COLS)[GY_COLS]
    return [GY_HEADER] + df.values.tolist()


def gy_export_xlsx(values):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    for r in values:
        ws.append(list(r))
    for i, col in enumerate(ws.columns, 1):
        width = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(50, max(8, width + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def gy_export_csv(values):
    buf = io.StringIO()
    csv.writer(buf).writerows(values)
    return buf.getvalue().encode("utf-8-sig")


# ---------------------------------------------------------------------------
# Interfață
# ---------------------------------------------------------------------------
st.markdown("""
<style>
.pos-code {font-size: 3.4rem; font-weight: 800; text-align: center; color: #fff;
  background: #0a7d32; border-radius: 16px; padding: .35em .2em; letter-spacing: .06em; margin: .3em 0;}
.pos-none {background: #b26a00; font-size: 2.2rem;}
.pos-label {text-align:center; font-size: 1.05rem; color: #555; margin-bottom: -.4em;}
.stTabs [data-baseweb="tab-list"] {flex-wrap: wrap; gap: .25rem;}
.stTabs [data-baseweb="tab"] {font-size: 1.05rem; padding: .4rem .7rem;}
div[data-testid="stTextInput"] input {font-size: 1.25rem;}
</style>
""", unsafe_allow_html=True)


def pos_card(code, label="POZIȚIE RAFT", legacy=""):
    if code:
        st.markdown(f'<div class="pos-label">{label}</div><div class="pos-code">{code}</div>', unsafe_allow_html=True)
    else:
        extra = f"<br><span style='font-size:1.3rem'>Locație veche GY: {legacy}</span>" if legacy else ""
        st.markdown(f'<div class="pos-label">{label}</div><div class="pos-code pos-none">FĂRĂ POZIȚIE R-N-P{extra}</div>',
                    unsafe_allow_html=True)


def tyre_table(rows):
    if not len(rows):
        st.caption("Nu există anvelope înregistrate pentru această mașină.")
        return
    t = rows[["BRAND", "MaterialDescription", "ProductGroup", "TreadDepth", "DOT", "WheelType", "StorageDate", NOTE]].copy()
    t["ProductGroup"] = t["ProductGroup"].map(lambda s: SEASON_RO.get(s, s))
    t.insert(0, "Nr.", range(1, len(t) + 1))
    show_df(t)


def set_header(h, rows):
    days = set_days(h, rows)
    models = ", ".join(uniq(rows["Make/Model"])) if len(rows) else ""
    vins = ", ".join(uniq(rows["Chassis Num"])) if len(rows) else ""
    st.markdown(
        f"**Flotă / client:** {h['FleetName'] or '-'}"
        + (f"  ·  {people_line(h)}" if people_line(h) else "") + "  \n"
        f"**Mașină:** {models or '-'}  ·  **VIN:** {vins or '-'}  \n"
        f"**Pe raft:** {len(rows)} anvelope · sezon "
        f"{'/'.join(SEASON_RO.get(s, s) for s in uniq(rows['ProductGroup'])) if len(rows) else '-'}  \n"
        f"**Depozitat / ultim schimb:** {h['StorageDate'] or '-'}" + (f" ({days} zile)" if days is not None else "")
        + (f"  \n**Telefon:** {h['Phone']}" if h["Phone"] else ""))
    if days is not None and days > CFG["days"]:
        st.warning(f"Setul stă în hotel de {days} zile (peste {CFG['days']}) – se aplică facturare suplimentară.")
    if len(rows) and any(is_worn(x) for x in rows["TreadDepth"]):
        st.error(f"⚠️ Setul de pe raft are anvelope sub {CFG['worn_mm']:g} mm – recomandă anvelope noi înainte de montaj.")
    if len(rows) and len(rows) != 4:
        st.info(f"Atenție: în evidență sunt {len(rows)} anvelope (nu 4).")


def tyre_entry(prefix, defaults, n, per_tyre_mode):
    """Câmpurile pentru setul care intră pe raft (în interiorul unui formular). Întoarce funcția care produce lista."""
    st.markdown(f"**Valori comune pentru cele {n} anvelope**")
    c1, c2 = st.columns(2)
    brand = c1.text_input("Marcă *", value=defaults.get("BRAND", ""), key=f"{prefix}_brand")
    desc = c2.text_input("Dimensiune / model * (ex: 205/55R16 91V PRIMACY 4)",
                         value=defaults.get("MaterialDescription", ""), key=f"{prefix}_desc")
    c3, c4 = st.columns(2)
    ds = defaults.get("ProductGroup", "Winter")
    season = c3.radio("Sezon", SEASONS, index=SEASONS.index(ds) if ds in SEASONS else 0, horizontal=True,
                      format_func=lambda s: SEASON_RO[s], key=f"{prefix}_season")
    dw = defaults.get("WheelType", "Tyre Only")
    wheel = c4.radio("Jantă", WHEEL_TYPES, index=WHEEL_TYPES.index(dw) if dw in WHEEL_TYPES else 0, horizontal=True,
                     format_func=lambda s: WHEEL_RO[s], key=f"{prefix}_wheel")
    c5, c6, c7 = st.columns(3)
    tread = c5.text_input("Profil (mm) *" + (" – comun" if per_tyre_mode else ""), key=f"{prefix}_tread",
                          placeholder="ex: 6 sau 5,5")
    dot = c6.text_input("DOT", key=f"{prefix}_dot", placeholder="ex: 2324")
    note = c7.text_input("Observații / accesorii", key=f"{prefix}_note")
    edited = None
    if per_tyre_mode:
        st.markdown("**Pe fiecare anvelopă** (căsuța goală = valoarea comună de mai sus)")
        base = pd.DataFrame({"Anvelopa": [str(i + 1) for i in range(n)], "Marcă": [""] * n, "Dimensiune / model": [""] * n,
                             "Profil (mm)": [""] * n, "DOT": [""] * n, "Observații": [""] * n})
        edited = st.data_editor(base, hide_index=True, disabled=["Anvelopa"], key=f"{prefix}_editor_{n}",
                                num_rows="fixed")

    def collect():
        common = {"BRAND": brand, "MaterialDescription": desc, "ProductGroup": season, "WheelType": wheel,
                  "TreadDepth": tread, "DOT": dot, NOTE: note}
        per = None
        if edited is not None:
            ren = {"Marcă": "BRAND", "Dimensiune / model": "MaterialDescription", "Profil (mm)": "TreadDepth",
                   "DOT": "DOT", "Observații": NOTE}
            per = [{ren[k]: ("" if pd.isna(v) else str(v)) for k, v in r.items() if k in ren}
                   for r in pd.DataFrame(edited).to_dict("records")]
        return expand_tyres(common, n, per)
    return collect


def people_line(d):
    parts = []
    if d.get("UserName", "") or d.get("UserPhone", ""):
        parts.append(f"**Utilizator:** {d.get('UserName', '') or '-'}" + (f" ({d['UserPhone']})" if d.get("UserPhone", "") else ""))
    if d.get("ClientCompany", ""):
        parts.append(f"**Firmă client:** {d['ClientCompany']}")
    return "  ·  ".join(parts)


RTY_EDIT = {"MaterialDescription": "Dimensiune *", "BRAND": "Marcă", "TyreModel": "Model", "ProductGroup": "Sezon",
            "DOT": "DOT", "TreadDepth": "Profil (mm)", "Axle": "Poziție pe mașină", "Note": "Observații"}


def rtyres_editor(key, rows=None, n_default=4):
    """Editor un rând pe anvelopă (rânduri adăugabile / ștergibile). Întoarce funcția care dă lista de anvelope."""
    if rows is None or not len(rows):
        base = pd.DataFrame({c: [""] * n_default for c in RTY_EDIT})
    else:
        base = pd.DataFrame(rows)[list(RTY_EDIT)].fillna("").astype(str).reset_index(drop=True)
    base["ProductGroup"] = base["ProductGroup"].map(lambda s: SEASON_RO.get(norm_season(s), "") if s else "")
    view = base.rename(columns=RTY_EDIT)
    cfg = {
        "Sezon": st.column_config.SelectboxColumn("Sezon", options=["IARNA", "VARA", "ALL SEASON"]),
        "Poziție pe mașină": st.column_config.SelectboxColumn("Poziție pe mașină", options=AXLES),
        "Dimensiune *": st.column_config.TextColumn("Dimensiune *", help="ex: 205/55R16 91V"),
        "Profil (mm)": st.column_config.TextColumn("Profil (mm)", help="uzură în mm, ex: 7 sau 6,5"),
    }
    edited = st.data_editor(view, num_rows="dynamic", hide_index=True, key=key, column_config=cfg,
                            width="stretch")

    def collect(fill_from_first=False):
        inv = {v: k for k, v in RTY_EDIT.items()}
        out = []
        for r in pd.DataFrame(edited).to_dict("records"):
            t = {inv[k]: ("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)) for k, v in r.items() if k in inv}
            out.append(t)
        out = [t for t in out if any(str(v).strip() for v in t.values())]
        if fill_from_first and out:
            first = out[0]
            for t in out[1:]:
                for k in ("MaterialDescription", "BRAND", "TyreModel", "ProductGroup", "DOT", "TreadDepth"):
                    if not str(t.get(k, "")).strip():
                        t[k] = first.get(k, "")
        return out
    return collect


def rtyres_table(t):
    if not len(t):
        st.caption("Nu există anvelope înregistrate pe această recepție.")
        return
    v = t[["TyreNo"] + list(RTY_EDIT)].copy()
    v["ProductGroup"] = v["ProductGroup"].map(lambda s: SEASON_RO.get(s, s))
    show_df(v)


def leasing_swap_panel(np_, orec, i):
    st.subheader("📦 Set trimis de leasing – recepționat, așteaptă montajul")
    ids = orec["ReceptionId"].tolist()
    if len(ids) > 1:
        st.warning(f"Mașina are {len(ids)} recepții deschise. Alege setul montat.")
    rid = st.selectbox("Recepție", ids, key=f"ls_rid_{np_}",
                       format_func=lambda x: f"{x} – {orec.set_index('ReceptionId').at[x, 'ReceptionDate']}")
    r = orec.set_index("ReceptionId").loc[rid].to_dict()
    r["ReceptionId"] = rid
    age = rec_age(r)
    st.markdown(f"**Flotă:** {r['FleetName'] or '-'}  ·  {people_line(r) or 'Utilizator / firmă client: -'}  \n"
                f"**Recepționat:** {r['ReceptionDate'] or '-'}" + (f" ({age} zile)" if age is not None else "")
                + f"  ·  **Locație așteptare:** {r['WaitingLocation'] or '-'}" + (f"  \n**Notă:** {r['Note']}" if r["Note"] else ""))
    if age is not None and age > RC_DAYS:
        st.warning(f"Setul așteaptă de {age} zile (peste {RC_DAYS}) – la sfârșit de sezon intră în My Way ca EXTRA DEPOZITARE.")
    rtyres_table(rec_tyres(rty_df, rid))
    has_dep = i is not None and hotel_df.at[i, "Status"] == ST_DEP
    replace = False
    assign = ""
    if has_dep:
        hh = hotel_df.loc[i]
        st.warning(f"Mașina are deja un set DEPOZITAT pe raft ({hh['PositionCode'] or 'fără poziție'}). Dacă montezi "
                   "setul recepționat, setul dat jos îl înlocuiește în evidență (setul vechi se arhivează).")
        replace = st.checkbox("Confirm: setul dat jos înlocuiește în evidență setul de pe raft", key=f"ls_repl_{np_}")
        assign = hh["PositionCode"]
    if not assign:
        free = free_positions_ordered(pos_df, hotel_df, r["FleetName"])
        opts = free["PositionCode"].tolist()
        if opts:
            fl = dict(zip(free["PositionCode"], free["FleetName"]))
            assign = st.selectbox("Poziție pentru setul dat jos", opts + [""], key=f"ls_assign_{np_}",
                                  format_func=lambda c: f"{c}  ({fl.get(c) or COMUN})" if c else "(fără poziție)")
        else:
            st.caption("Nu există poziții libere definite. Poți salva și fără poziție.")
    mt = rec_tyres(rty_df, rid)
    c1, c2 = st.columns(2)
    n = int(c1.number_input("Câte anvelope dai jos", 1, 6, 4, key=f"ls_n_{np_}"))
    mode = c2.radio("Mod completare", ["Set comun (aceleași valori)", "Pe fiecare anvelopă"], key=f"ls_mode_{np_}",
                    horizontal=True)
    rs = mt["ProductGroup"].iloc[0] if len(mt) else r.get("Season", "")
    with st.form(f"ls_swap_form_{np_}", clear_on_submit=True):
        st.markdown("**Setul dat jos de pe mașină (intră pe raft, DEPOZITAT)**")
        collect = tyre_entry(f"ls_{np_}", {"ProductGroup": other_season(rs)}, n, mode.startswith("Pe fiecare"))
        unote = st.text_input("Notă operator (opțional)", key=f"ls_note_{np_}")
        ok = st.form_submit_button("✅ Montat setul recepționat", type="primary")
    if ok:
        try:
            tyres = collect()
            code, worn = do_leasing_swap(rid, tyres, assign, unote.strip(), replace)
            flash(f"✅ Setul recepționat a fost montat pe {np_}. Setul dat jos ({len(tyres)} anv.) este DEPOZITAT la "
                  f"{code or '(fără poziție)'}. Fișa GY (schimb + depozitare) este în lista «De introdus în GY».")
            if worn:
                flash(f"⚠️ {worn} anvelope din setul dat jos au profil sub {CFG['worn_mm']:g} mm.", "warning")
            st.rerun()
        except BackendError as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001
            st.error(f"Eroare la salvarea schimbului: {e}")


def car_status_card(query, key="card"):
    """Fișa clară a mașinii: are anvelope în hotel? are anvelope recepționate? Caută după număr auto sau VIN."""
    res = resolve_car(query)
    if not res["by"]:
        return res
    plates, vins = res["plates"], res["vins"]
    if len(plates) > 1:
        st.warning("VIN-ul se potrivește cu mai multe mașini: " + ", ".join(plates) + ". Scrie VIN-ul complet sau numărul.")
    plate = plates[0] if plates else ""
    hi = find_row(hotel_df, plate) if plate else None
    h = hotel_df.loc[hi] if hi is not None else None
    recs = receptions_for(rec_df, plate, vins)
    op = recs[recs["Status"].str.upper() == RC_OPEN]
    src = (h if h is not None else (recs.iloc[-1] if len(recs) else {}))
    fleet = (h["FleetName"] if h is not None and h["FleetName"] else "") or (recs.iloc[-1]["FleetName"] if len(recs) else "")
    ppl = {k: (h[k] if h is not None and h[k] else "") or next((x for x in recs[k][::-1] if x), "") for k in CAR_PEOPLE} \
        if len(recs) or h is not None else {}
    with st.container(border=True):
        st.markdown(f"### 🚗 {plate or '(fără număr auto)'}" + (f"  ·  VIN {', '.join(vins)}" if vins else ""))
        st.markdown(f"**Flotă:** {fleet or '-'}" + (f"  ·  {people_line(ppl)}" if ppl and people_line(ppl) else ""))
        c1, c2 = st.columns(2)
        if h is not None and h["Status"] == ST_DEP:
            rows = tyres_of(ty_df, plate)
            seas = "/".join(SEASON_RO.get(s, s) for s in uniq(rows["ProductGroup"])) if len(rows) else SEASON_RO.get(h["Season"], h["Season"])
            c1.success(f"**Are anvelope în hotel: DA**  \nPoziție: {h['PositionCode'] or ('fără R-N-P' + (' – loc. veche ' + h['LegacyLocation'] if h['LegacyLocation'] else ''))}  \n"
                       f"Sezon: {seas or '-'} · {len(rows)} anv.  \nDepozitat: {h['StorageDate'] or '-'}")
        else:
            c1.info("**Are anvelope în hotel: NU**" + (f"  \n(ridicat pe {h['ExitDate'] or '-'})" if h is not None else ""))
        if len(op):
            lines = [f"{r['Condition'] or 'NOI'} · {r['ReceptionDate'] or '-'} · {r['Tyres']} anv."
                     + (f" · {r['WaitingLocation']}" if r["WaitingLocation"] else "") for _, r in op.iterrows()]
            c2.success("**Anvelope recepționate: DA**  \n" + "  \n".join(lines))
        else:
            c2.info("**Anvelope recepționate: NU**")
        closed = recs[recs["Status"].str.upper() != RC_OPEN]
        if len(closed):
            st.caption("Recepții închise: " + "; ".join(f"{r['ReceptionDate']} {r['Condition'] or ''} → {r['Status']}"
                                                         for _, r in closed.iterrows()))
    nolink = op[op["RegistrationNumber"].map(norm_plate) == ""]
    if len(nolink):
        st.info("Recepția a venit doar cu VIN. Leag-o de numărul auto al mașinii:")
        for _, r in nolink.iterrows():
            with st.form(f"link_{key}_{r['ReceptionId']}"):
                c1, c2 = st.columns([3, 1])
                lp = c1.text_input(f"Număr auto pentru VIN {r['VIN']} ({r['ReceptionDate']})", value=plate)
                okl = c2.form_submit_button("🔗 Leagă")
            if okl:
                try:
                    do_link_reception(r["ReceptionId"], lp)
                    flash(f"✅ Recepția cu VIN {r['VIN']} a fost legată de {norm_plate(lp)}.")
                    st.rerun()
                except BackendError as e:
                    st.error(str(e))
    return res


def car_people_editor(h, key):
    with st.expander("✏️ Utilizator / firmă client"):
        with st.form(f"people_{key}"):
            c1, c2, c3 = st.columns(3)
            un = c1.text_input("Utilizator (nume)", value=h.get("UserName", ""))
            up = c2.text_input("Telefon utilizator", value=h.get("UserPhone", ""))
            cc = c3.text_input("Firmă client (contract leasing)", value=h.get("ClientCompany", ""))
            vn = st.text_input("VIN / serie șasiu", value=h.get("VIN", "") or (car_vins(h["RegistrationNumber"]) or [""])[0])
            okp = st.form_submit_button("💾 Salvează")
        if okp:
            try:
                n_ch = do_edit_car_people(h["RegistrationNumber"], {"UserName": un, "UserPhone": up, "ClientCompany": cc, "VIN": vn})
                flash(f"✅ Date mașină actualizate ({n_ch} modificări)." if n_ch else "Nicio modificare.", "success" if n_ch else "info")
                st.rerun()
            except BackendError as e:
                st.error(str(e))


# --- conexiune ------------------------------------------------------------
st.title("🛞 MADYT – Hotel Anvelope")
try:
    init_msgs = initialize(CFG["demo"], CFG["spreadsheet_id"], CFG["demo_dir"])
    hotel_df = load(HOTEL)
    ty_df = load(TY)
    pos_df = load(POZ)
    rec_df = load(REC)
    rty_df = load(RTY)
    fise_df = load(FISE)
except BackendError as e:
    st.error(f"Nu mă pot conecta la baza de date. {e}")
    st.info("Vrei doar să testezi aplicația? Pornește-o în modul DEMO: pune `demo_mode = true` în secrets "
            "sau rulează cu variabila de mediu `MADYT_DEMO=1`. Detalii în README.md.")
    st.stop()
except Exception as e:  # noqa: BLE001
    st.error(f"Eroare neașteptată la conectarea cu Google Sheets: {e}")
    st.info("Verifică secrets (cheia contului de serviciu), ID-ul tabelului și dacă tabelul e partajat "
            "cu emailul contului de serviciu ca Editor. Pentru test fără Google folosește modul DEMO (MADYT_DEMO=1).")
    st.stop()

with st.sidebar:
    st.subheader("Setări sesiune")
    st.text_input("Operator (numele tău)", key="operator")
    st.caption(f"Sursă date: {backend().label}")
    st.caption(f"Prag uzură: {CFG['worn_mm']:g} mm · Termen depozitare: {CFG['days']} zile")
    if st.button("🔄 Reîncarcă datele"):
        clear_cache()
        st.rerun()

if CFG["demo"]:
    st.info("Mod DEMO: datele sunt salvate local în fișiere CSV, nu în Google Sheets.")
for m in init_msgs:
    st.info(m)
for kind, msg in st.session_state.pop("_flash", []):
    getattr(st, kind)(msg)

_open = open_receptions(rec_df)
_old = sum(1 for _, r in _open.iterrows() if (rec_age(r) or 0) > RC_DAYS)
_fst = fise_df["Status"].str.strip().str.upper().replace("", F_TODO).value_counts()
_mc = st.columns(2 + len(F_STATUSES))
_mc[0].metric("Recepții leasing deschise", len(_open))
_mc[1].metric(f"De introdus în My Way (>{RC_DAYS} zile)", _old)
for _k, _s in enumerate(F_STATUSES):
    _mc[2 + _k].metric(f"Fișe GY: {F_RO[_s]}", int(_fst.get(_s, 0)))

tabs = st.tabs(["🔁 Schimb sezon", "🔍 Căutare stoc", "📦 Recepție client nou", "🚚 Recepție leasing",
                "🚪 Ieșire din hotel", "🗄️ Rafturi", "📊 Rapoarte", "🧾 Fișe GY", "📅 Sfârșit sezon / My Way",
                "⚙️ Administrare poziții", "🔄 GY Fleet"])

# --- 1. Schimb sezon --------------------------------------------------------
with tabs[0]:
    st.header("Schimb de sezon")
    plate = st.text_input("Număr auto sau VIN (complet sau ultimele 6+ caractere)", key="swap_plate",
                          placeholder="ex: B123ABC sau VF1...123456").strip()
    if plate:
        rs_ = car_status_card(plate, "swap")
        if rs_["plates"]:
            plate = rs_["plates"][0]
        np_ = norm_plate(plate)
        i = find_row(hotel_df, plate) if (rs_["plates"] or not rs_["by"]) else None
        orec = receptions_for(rec_df, np_ if rs_["plates"] or not rs_["by"] else "", rs_["vins"], only_open=True)
        orec = orec[orec["RegistrationNumber"].map(norm_plate) != ""]  # cele doar cu VIN se leagă întâi (fișa de mai sus)
        show_regular = True
        if len(orec):
            leasing_swap_panel(np_, orec, i)
            if i is not None and hotel_df.at[i, "Status"] == ST_DEP:
                st.divider()
                show_regular = st.checkbox("Arată schimbul obișnuit (montez setul de pe raft, nu cel recepționat)",
                                           key=f"swap_regular_{np_}")
        if i is None:
            if not len(orec) and not rs_["by"]:
                st.warning(f"Mașina {np_} nu are niciun set în hotel. Folosește tab-ul **Recepție client nou** "
                           "(sau **Recepție leasing** dacă setul a venit de la GY).")
        elif hotel_df.at[i, "Status"] != ST_DEP:
            if not len(orec):
                st.warning(f"Setul mașinii {np_} a fost RIDICAT pe {hotel_df.at[i, 'ExitDate'] or '-'}. "
                           "Pentru o nouă depozitare folosește tab-ul **Recepție client nou**.")
        elif show_regular:
            h = hotel_df.loc[i]
            rows = tyres_of(ty_df, plate)
            st.subheader(f"🚗 {h['RegistrationNumber']}")
            pos_card(h["PositionCode"], legacy=h["LegacyLocation"])
            set_header(h, rows)
            car_people_editor(h, f"swap_{np_}")
            tyre_table(rows)

            assign = ""
            if not h["PositionCode"]:
                st.warning("Setul nu are încă poziție R-N-P. Alege poziția în care pui setul dat jos "
                           "(propunerea = prima poziție liberă a flotei).")
                free = free_positions_ordered(pos_df, hotel_df, h["FleetName"])
                opts = free["PositionCode"].tolist()
                if opts:
                    fl = dict(zip(free["PositionCode"], free["FleetName"]))
                    assign = st.selectbox("Poziție", opts + [""], key=f"swap_assign_{np_}",
                                          format_func=lambda c: f"{c}  ({fl.get(c) or COMUN})" if c else "(fără poziție)")
                else:
                    st.caption("Nu există poziții libere definite. Poți salva și fără poziție.")

            st.markdown(
                f"1. Ia setul de la **{h['PositionCode'] or (('locația veche ' + h['LegacyLocation']) if h['LegacyLocation'] else '-')}** "
                "și montează-l pe mașină.  \n"
                f"2. Pune setul dat jos în **{h['PositionCode'] or assign or 'poziția aleasă'}**.  \n"
                "3. Completează datele setului dat jos și confirmă.")
            c1, c2 = st.columns(2)
            n = int(c1.number_input("Câte anvelope dai jos", 1, 6, 4, key=f"swap_n_{np_}"))
            mode = c2.radio("Mod completare", ["Set comun (aceleași valori)", "Pe fiecare anvelopă"],
                            key=f"swap_mode_{np_}", horizontal=True)
            defaults = {"ProductGroup": other_season(rows["ProductGroup"].iloc[0] if len(rows) else h["Season"]),
                        "WheelType": rows["WheelType"].iloc[0] if len(rows) and rows["WheelType"].iloc[0] else "Tyre Only"}
            with st.form("swap_form", clear_on_submit=True):
                st.markdown("**Setul dat jos de pe mașină (intră acum pe raft)**")
                collect = tyre_entry(f"sw_{np_}", defaults, n, mode.startswith("Pe fiecare"))
                unote = st.text_input("Notă operator (opțional)")
                ok = st.form_submit_button("✅ Confirmă schimbul", type="primary")
            if ok:
                try:
                    tyres = collect()
                    code, worn = do_swap(h["RegistrationNumber"], tyres, assign, unote.strip())
                    flash(f"✅ Schimb înregistrat pentru {h['RegistrationNumber']} ({len(tyres)} anvelope). "
                          f"Setul dat jos este la poziția {code or '(fără poziție)'}.")
                    if worn:
                        flash(f"⚠️ {worn} anvelope din setul dat jos au profil sub {CFG['worn_mm']:g} mm – recomandă "
                              "clientului anvelope noi (apare și în Rapoarte).", "warning")
                    st.rerun()
                except BackendError as e:
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Eroare la salvarea schimbului: {e}")

            ist = load(IST)
            hh = ist[ist["RegistrationNumber"].map(norm_plate) == np_]
            if len(hh):
                with st.expander(f"Istoric mașină ({len(hh)} înregistrări)"):
                    show_df(hh.iloc[::-1])

# --- 2. Căutare stoc ------------------------------------------------------
with tabs[1]:
    st.header("Căutare în stoc")
    sets_df = build_sets(hotel_df, ty_df)
    q = st.text_input("Caută după număr auto, VIN, flotă, anvelopă, poziție…", key="search_q").strip().upper()
    res = sets_df
    if q and len(res):
        nq = norm_plate(q)
        mask = res.astype(str).apply(lambda col: col.str.upper().str.contains(q, regex=False)).any(axis=1)
        if nq:
            mask |= res["RegistrationNumber"].map(norm_plate).str.contains(nq, regex=False)
        res = res[mask]
    if q:
        car_status_card(q, "search")
    st.caption(f"{len(res)} seturi în hotel")
    show_df(res)
    if q and len(res) == 1:
        st.markdown("**Anvelopele setului**")
        tyre_table(tyres_of(ty_df, res.iloc[0]["RegistrationNumber"]))
    rid = hotel_df[hotel_df["Status"] == ST_RID]
    if len(rid):
        with st.expander(f"Seturi ridicate ({len(rid)})"):
            show_df(rid)

# --- 3. Recepție client nou ----------------------------------------------
with tabs[2]:
    st.header("Recepție client nou")
    fleets = fleets_with_rows(pos_df)
    known = sorted({f.strip() for f in hotel_df["FleetName"] if f.strip()} - set(fleets))
    choice = st.selectbox("Tip client", ["Client individual (rânduri comune)"] + [f"Flotă: {f}" for f in fleets + known]
                          + ["Altă flotă / firmă…"], key="rec_type")
    if choice.startswith("Flotă: "):
        fleet = client_name = choice[len("Flotă: "):]
    elif choice.startswith("Altă"):
        fleet = client_name = st.text_input("Nume flotă / firmă *", key="rec_fleet_new").strip()
    else:
        fleet = ""
        client_name = st.text_input("Nume client *", key="rec_client").strip()

    free = free_positions_ordered(pos_df, hotel_df, fleet)
    opts = free["PositionCode"].tolist()
    fl_map = dict(zip(free["PositionCode"], free["FleetName"]))
    if opts:
        code = st.selectbox("Poziție propusă (prima liberă)", opts + [""], key=f"rec_pos_{fleet.upper()}",
                            format_func=lambda c: f"{c}  ({fl_map.get(c) or COMUN})" if c else "(fără poziție)")
        if code:
            pos_card(code, "PUNE SETUL LA")
        if fleet and code and fl_map.get(code, "").upper() != fleet.upper():
            st.caption("Flota nu are (sau nu mai are) poziții libere dedicate – am propus o poziție comună.")
    else:
        code = ""
        st.warning("Nu există poziții libere. Generează poziții în Administrare poziții (sau salvează fără poziție).")
    c1, c2 = st.columns(2)
    n_r = int(c1.number_input("Număr anvelope", 1, 6, 4, key="rec_n"))
    mode_r = c2.radio("Mod completare", ["Set comun (aceleași valori)", "Pe fiecare anvelopă"], key="rec_mode",
                      horizontal=True)
    with st.form("rec_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        plate_n = c1.text_input("Număr auto *").strip().upper()
        phone = c2.text_input("Telefon")
        email = c3.text_input("Email")
        vin = c1.text_input("Serie șasiu (VIN)").strip().upper()
        model = c2.text_input("Marcă / model mașină")
        sold_to = c3.text_input("Cod client GY (SOLD-TO, opțional)")
        collect_r = tyre_entry("rec", {"ProductGroup": "Winter"}, n_r, mode_r.startswith("Pe fiecare"))
        ok_n = st.form_submit_button("💾 Salvează recepția", type="primary")
    if ok_n:
        if not plate_n or not client_name:
            st.error("Completează numărul auto și clientul / flota.")
        else:
            try:
                tyres = collect_r()
                do_reception({"RegistrationNumber": plate_n, "FleetName": client_name, "Chassis Num": vin,
                              "Make/Model": model.strip(), "SOLD-TO": sold_to.strip(), "Phone": phone.strip(),
                              "Email": email.strip()}, tyres, code)
                flash(f"✅ Setul mașinii {norm_plate(plate_n)} ({len(tyres)} anvelope) a fost înregistrat la poziția "
                      f"{code or '(fără poziție)'}.")
                if any(is_worn(t["TreadDepth"]) for t in tyres):
                    flash(f"⚠️ Profil sub {CFG['worn_mm']:g} mm – recomandă clientului anvelope noi.", "warning")
                st.rerun()
            except BackendError as e:
                st.error(str(e))
            except Exception as e:  # noqa: BLE001
                st.error(f"Eroare la salvarea recepției: {e}")

# --- 3b. Recepție leasing ----------------------------------------------------
with tabs[3]:
    st.header("Recepție leasing (set trimis de Goodyear Fleet pentru o mașină)")
    st.caption("Setul vine de la GY pentru o mașină de leasing și așteaptă clientul. La montaj (tab-ul Schimb sezon) "
               "setul dat jos intră pe raft și se creează fișa GY. Dacă mașina nu vine, la sfârșit de sezon setul se "
               "introduce în My Way (EXTRA DEPOZITARE).")
    lt = st.radio("Secțiune", ["➕ Recepție nouă", "📋 Lista recepțiilor", "✏️ Editează recepție", "📥 Import din Excel"],
                  horizontal=True, key="ls_section", label_visibility="collapsed")
    fleets_l = all_fleets(hotel_df, rec_df, pos_df)

    if lt.startswith("➕"):
        c1, c2, c3 = st.columns(3)
        lp = c1.text_input("Număr auto (gol dacă a venit doar VIN)", key="lr_plate", placeholder="ex: B123ABC")
        lpn = norm_plate(lp)
        lv = c2.text_input("VIN / serie șasiu", key="lr_vin", placeholder="opțional dacă ai numărul")
        lvn = norm_vin(lv)
        if lp.strip() or lv.strip():
            c1.caption(f"Se salvează ca: **{lpn or '-'}**" + (f" · VIN **{lvn}**" if lvn else ""))
        if lv.strip() and not lvn:
            c2.error("VIN-ul trebuie să aibă cel puțin 6 caractere.")
        if not lpn and lvn:
            rv = resolve_car(lvn)
            if len(rv["plates"]) == 1:
                lpn = rv["plates"][0]
                c1.info(f"VIN-ul aparține mașinii **{lpn}** – recepția se leagă automat.")
        hi = find_row(hotel_df, lpn) if lpn else None
        hrow = hotel_df.loc[hi] if hi is not None else None
        fdef = hrow["FleetName"] if hrow is not None and hrow["FleetName"] in fleets_l else None
        fsel_l = c3.selectbox("Flotă (leasing) *", fleets_l + ["Altă flotă…"],
                              index=(fleets_l.index(fdef) if fdef else 0), key=f"lr_fleet_{lpn}")
        fleet_l = c3.text_input("Nume flotă *", key="lr_fleet_new").strip() if fsel_l == "Altă flotă…" else fsel_l
        dup = open_receptions(rec_df, lpn or None, lvn) if (lpn or lvn) else rec_df.iloc[0:0]
        if len(dup):
            st.warning(f"⚠️ Mașina {lpn or 'VIN ' + lvn} are deja {len(dup)} recepție/recepții deschise (RECEPTIONAT): "
                       + ", ".join(f"{r['ReceptionDate']} ({r['Tyres']} anv.)" for _, r in dup.iterrows())
                       + ". Salvează doar dacă este un set diferit.")
        if hrow is not None:
            st.info(f"Mașina este deja în evidența hotelului: {hrow['Status']}"
                    + (f" la {hrow['PositionCode']}" if hrow["PositionCode"] else "") + f" · flotă {hrow['FleetName'] or '-'}")
        with st.form("lr_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            rdate = c1.date_input("Data recepției", value=date.today(), format="DD.MM.YYYY")
            cond = c2.radio("Anvelope", rimp.CONDITIONS, horizontal=True)
            wloc = c3.text_input("Locație de așteptare", placeholder="ex: container 2, palet A")
            lnote = st.text_input("Notă")
            c1, c2, c3 = st.columns(3)
            pv_ = (lambda k: hrow[k] if hrow is not None else "")
            uname = c1.text_input("Utilizator (nume)", value=pv_("UserName"))
            uphone = c2.text_input("Telefon utilizator (opțional)", value=pv_("UserPhone"))
            ccomp = c3.text_input("Firmă client (contract leasing)", value=pv_("ClientCompany"))
            st.markdown("**Anvelopele primite – câte un rând pe anvelopă** (adaugă / șterge rânduri din tabel)")
            collect_l = rtyres_editor(f"lr_tyres_{lpn}_{ver()}")
            fill = st.checkbox("Completează căsuțele goale cu valorile primei anvelope", value=True)
            force = st.checkbox("Confirm: este un set nou, deși mașina are deja o recepție deschisă") if len(dup) else False
            ok_l = st.form_submit_button("💾 Salvează recepția", type="primary")
        if ok_l:
            if (not lpn and not lvn) or not fleet_l:
                st.error("Completează numărul auto sau VIN-ul, și flota.")
            else:
                try:
                    tyres = collect_l(fill)
                    rid = do_leasing_reception({"RegistrationNumber": lpn, "VIN": lv, "Condition": cond,
                                                "FleetName": fleet_l, "ReceptionDate": rdate,
                                                "WaitingLocation": wloc, "Note": lnote, "UserName": uname,
                                                "UserPhone": uphone, "ClientCompany": ccomp}, tyres, bool(force))
                    flash(f"✅ Recepție leasing salvată pentru {lpn or 'VIN ' + lvn} ({len(clean_rtyres(tyres))} anvelope) – {rid}.")
                    st.rerun()
                except BackendError as e:
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Eroare la salvarea recepției: {e}")

    elif lt.startswith("📋"):
        c1, c2, c3 = st.columns(3)
        sts = c1.multiselect("Status", [RC_OPEN, RC_SWAP, RC_EXTRA], default=[RC_OPEN], key="lr_list_st")
        fl_f = c2.multiselect("Flotă", fleets_l, key="lr_list_fl")
        q_l = c3.text_input("Caută (număr, utilizator, firmă…)", key="lr_list_q").strip().upper()
        v = rec_df.copy()
        if sts:
            v = v[v["Status"].str.upper().isin(sts)]
        if fl_f:
            v = v[v["FleetName"].isin(fl_f)]
        if q_l:
            v = v[v.astype(str).apply(lambda c: c.str.upper().str.contains(q_l, regex=False)).any(axis=1)]
        v = v.assign(Zile=v.apply(lambda r: rec_age(r), axis=1)).sort_values("ReceptionDate")
        st.caption(f"{len(v)} recepții")
        show_df(v[["RegistrationNumber", "VIN", "Condition", "FleetName", "UserName", "UserPhone", "ClientCompany",
                   "ReceptionDate", "Zile", "Tyres", "Season", "WaitingLocation", "Status", "SwapDate", "MyWayDate", "Note", "ReceptionId"]])
        if len(v):
            st.download_button("⬇️ Descarcă lista (CSV)", v.to_csv(index=False).encode("utf-8-sig"), "receptii_leasing.csv",
                               "text/csv")
            sel = st.selectbox("Vezi anvelopele recepției", v["ReceptionId"].tolist(), key="lr_list_sel",
                               format_func=lambda x: f"{v.set_index('ReceptionId').at[x, 'RegistrationNumber'] or 'VIN ' + v.set_index('ReceptionId').at[x, 'VIN']} – {x}")
            rtyres_table(rec_tyres(rty_df, sel))

    elif lt.startswith("✏️"):
        if rec_df.empty:
            st.info("Nu există recepții.")
        else:
            q_e = norm_plate(st.text_input("Număr auto sau VIN", key="lr_edit_q"))
            cand = rec_df[rec_df["RegistrationNumber"].map(norm_plate).str.contains(q_e, regex=False)
                          | rec_df["VIN"].map(norm_vin).str.contains(q_e, regex=False)] if q_e else rec_df
            cand = cand.iloc[::-1]
            if cand.empty:
                st.warning("Nicio recepție pentru acest număr.")
            else:
                rid_e = st.selectbox("Recepție", cand["ReceptionId"].tolist(), key="lr_edit_sel",
                                     format_func=lambda x: (lambda r: f"{r['RegistrationNumber'] or 'VIN ' + r['VIN']} · {r['ReceptionDate']} · "
                                                            f"{r['Status']} · {r['Tyres']} anv.")(cand.set_index('ReceptionId').loc[x]))
                r_e = rec_df[rec_df["ReceptionId"] == rid_e].iloc[0]
                if r_e["Status"].upper() != RC_OPEN:
                    st.info(f"Recepția are statusul {r_e['Status']} – modificările se salvează și se scriu în Istoric.")
                with st.form(f"lr_edit_form_{rid_e}"):
                    c1, c2, c3 = st.columns(3)
                    e_fl = c1.text_input("Flotă", value=r_e["FleetName"])
                    e_dt = c2.text_input("Data recepției (AAAA-LL-ZZ)", value=r_e["ReceptionDate"])
                    e_wl = c3.text_input("Locație de așteptare", value=r_e["WaitingLocation"])
                    c1, c2, c3 = st.columns(3)
                    e_un = c1.text_input("Utilizator (nume)", value=r_e["UserName"])
                    e_up = c2.text_input("Telefon utilizator", value=r_e["UserPhone"])
                    e_cc = c3.text_input("Firmă client", value=r_e["ClientCompany"])
                    c1, c2, c3 = st.columns(3)
                    e_pl = c1.text_input("Număr auto (leagă recepția de mașină)", value=r_e["RegistrationNumber"])
                    e_vn = c2.text_input("VIN / serie șasiu", value=r_e["VIN"])
                    e_cd = c3.radio("Anvelope", rimp.CONDITIONS, horizontal=True,
                                    index=rimp.CONDITIONS.index(r_e["Condition"]) if r_e["Condition"] in rimp.CONDITIONS else 0)
                    e_nt = st.text_input("Notă", value=r_e["Note"])
                    st.markdown("**Anvelope** (modifică direct în tabel; adaugă / șterge rânduri)")
                    collect_e = rtyres_editor(f"lr_edit_t_{rid_e}_{ver()}", rec_tyres(rty_df, rid_e))
                    ok_e2 = st.form_submit_button("💾 Salvează modificările", type="primary")
                if ok_e2:
                    try:
                        if pd.isna(parse_date(e_dt)):
                            raise BackendError("Data recepției nu este validă (ex: 2026-11-03).")
                        if norm_plate(e_pl) != norm_plate(r_e["RegistrationNumber"]):
                            if not norm_plate(e_pl):
                                raise BackendError("Numărul auto nu poate fi șters (doar schimbat).")
                            do_link_reception(rid_e, e_pl)
                        n_ch = do_edit_reception(rid_e, {"VIN": e_vn, "Condition": e_cd,
                                                         "FleetName": e_fl, "ReceptionDate": e_dt.strip(),
                                                         "WaitingLocation": e_wl, "Note": e_nt, "UserName": e_un,
                                                         "UserPhone": e_up, "ClientCompany": e_cc}, collect_e())
                        flash(f"✅ {n_ch} modificări salvate și trecute în Istoric." if n_ch else "Nicio modificare.",
                              "success" if n_ch else "info")
                        st.rerun()
                    except BackendError as e:
                        st.error(str(e))
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Eroare la salvare: {e}")
                ih = load(IST)
                ih = ih[ih["Details"].str.contains(rid_e, regex=False)]
                if len(ih):
                    with st.expander(f"Istoric recepție ({len(ih)})"):
                        show_df(ih.iloc[::-1])

    else:
        st.caption("Încarcă livrarea/exportul GY (.xlsx sau .csv), câte un rând pe anvelopă. Se creează câte o recepție "
                   "(RECEPTIONAT) pe fiecare număr auto. Coloanele se potrivesc automat; le poți corecta manual.")
        up_l = st.file_uploader("Fișier", type=["xlsx", "xlsm", "xls", "csv"], key="lr_import_file")
        if up_l is not None:
            try:
                raw_l = rimp.read_file(up_l.name, up_l.getvalue())
            except Exception as e:  # noqa: BLE001
                raw_l = None
                st.error(f"Nu pot citi fișierul: {e}")
            if raw_l is not None:
                st.caption(f"{len(raw_l)} rânduri, {len(raw_l.columns)} coloane.")
                amap = rimp.auto_map(raw_l.columns)
                cols_opt = ["(nu există)"] + list(raw_l.columns)
                with st.expander("Potrivire coloane", expanded=bool(rimp.missing_required(amap))):
                    mapping = {}
                    cc_ = st.columns(3)
                    for k, f in enumerate(rimp.FIELDS):
                        dflt = amap.get(f)
                        ch_ = cc_[k % 3].selectbox(rimp.LABELS_RO[f], cols_opt,
                                                   index=cols_opt.index(dflt) if dflt in cols_opt else 0,
                                                   key=f"lr_map_{f}")
                        if ch_ != "(nu există)":
                            mapping[f] = ch_
                c1, c2, c3 = st.columns(3)
                dfl = c1.selectbox("Flotă implicită (dacă lipsește în fișier)", [""] + fleets_l, key="lr_imp_fleet")
                rdate_i = c2.date_input("Data recepției", value=date.today(), format="DD.MM.YYYY", key="lr_imp_date")
                wloc_i = c3.text_input("Locație de așteptare", key="lr_imp_wloc")
                cond_i = st.radio("Anvelope (dacă fișierul nu are coloana Stare)", rimp.CONDITIONS, horizontal=True,
                                  key="lr_imp_cond")
                orc_ = open_receptions(rec_df)
                recs_i, warns_i, skipped_i = rimp.build_plan(raw_l, mapping, set(orc_["RegistrationNumber"]), dfl,
                                                             set(orc_["VIN"]), cond_i)
                for r_ in recs_i:  # VIN cunoscut -> număr auto
                    if not r_["RegistrationNumber"] and r_["VIN"]:
                        rv = resolve_car(r_["VIN"])
                        if len(rv["plates"]) == 1:
                            r_["RegistrationNumber"] = rv["plates"][0]
                c1, c2, c3 = st.columns(3)
                c1.metric("Mașini (recepții)", len(recs_i))
                c2.metric("Anvelope", sum(len(r["tyres"]) for r in recs_i))
                c3.metric("Rânduri ignorate (fără număr)", skipped_i)
                if warns_i:
                    with st.expander(f"⚠️ Avertismente ({len(warns_i)})", expanded=True):
                        st.markdown("\n".join(f"- {w}" for w in warns_i))
                if recs_i:
                    show_df(rimp.plan_table(recs_i), rename=False)
                    pl_i = st.selectbox("Vezi anvelopele unei mașini", list(range(len(recs_i))), key="lr_imp_view",
                                        format_func=lambda k: recs_i[k]["RegistrationNumber"] or "VIN " + recs_i[k]["VIN"])
                    show_df(pd.DataFrame(recs_i[pl_i]["tyres"]))
                    skip_open = st.checkbox("Sari peste mașinile care au deja o recepție deschisă", value=True,
                                            key="lr_imp_skip")
                    if st.button(f"✅ Creează {len(recs_i)} recepții", type="primary", key="lr_imp_go",
                                 disabled=bool(rimp.missing_required(mapping))):
                        try:
                            created, skipped = do_bulk_leasing_reception(recs_i, rdate_i, wloc_i.strip(), skip_open,
                                                                         up_l.name)
                            flash(f"✅ {len(created)} recepții create din {up_l.name}."
                                  + (f" Sărite: {', '.join(skipped)}." if skipped else ""))
                            st.rerun()
                        except Exception as e:  # noqa: BLE001
                            st.error(f"Eroare la import: {e}")

# --- 4. Ieșire din hotel ---------------------------------------------------
with tabs[4]:
    st.header("Ieșire din hotel (clientul își ia setul definitiv)")
    plate_e = st.text_input("Număr auto", key="exit_plate").strip()
    if plate_e:
        i = find_row(hotel_df, plate_e, only_status=ST_DEP)
        if i is None:
            st.warning("Nu există set DEPOZITAT pentru acest număr.")
        else:
            h = hotel_df.loc[i]
            rows = tyres_of(ty_df, plate_e)
            st.subheader(f"🚗 {h['RegistrationNumber']}")
            pos_card(h["PositionCode"], "IA SETUL DE LA", legacy=h["LegacyLocation"])
            set_header(h, rows)
            tyre_table(rows)
            with st.form("exit_form", clear_on_submit=True):
                note_e = st.text_input("Motiv / notă (opțional)")
                conf = st.checkbox("Confirm că setul a fost predat clientului")
                ok_e = st.form_submit_button("🚪 Înregistrează ieșirea", type="primary")
            if ok_e:
                if not conf:
                    st.error("Bifează confirmarea predării.")
                else:
                    try:
                        c = do_exit(h["RegistrationNumber"], note_e.strip())
                        flash(f"✅ Ieșire înregistrată pentru {h['RegistrationNumber']}. Poziția {c or '-'} este acum liberă.")
                        st.rerun()
                    except BackendError as e:
                        st.error(str(e))
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Eroare la înregistrarea ieșirii: {e}")

# --- 5. Rafturi -------------------------------------------------------------
with tabs[5]:
    st.header("Rafturi și ocupare")
    if pos_df.empty:
        st.info("Nu există poziții definite. Generează-le în tab-ul Administrare poziții.")
    else:
        pv = sync_positions(hotel_df, pos_df)
        pv["Ocupat"] = pv["OccupiedPlate"] != ""
        c1, c2, c3 = st.columns(3)
        c1.metric("Poziții totale", len(pv))
        c2.metric("Ocupate", int(pv["Ocupat"].sum()))
        c3.metric("Libere", int((~pv["Ocupat"]).sum()))
        pv["Flota"] = pv["FleetName"].replace("", COMUN)
        st.subheader("Pe flote")
        g = pv.groupby("Flota").agg(Rânduri=("Row", lambda s: ", ".join(sorted(set(s), key=int_key))),
                                    Total=("PositionCode", "count"), Ocupate=("Ocupat", "sum")).reset_index()
        g["Libere"] = g["Total"] - g["Ocupate"]
        show_df(g, rename=False)
        st.subheader("Hartă rând")
        rows_r = sorted(set(pv["Row"]), key=int_key)
        rsel = st.selectbox("Rând", rows_r, format_func=lambda x: f"R{x} – {pv[pv['Row'] == x]['Flota'].iloc[0]}")
        sub = pv[pv["Row"] == rsel].copy()
        sub["Cell"] = sub["OccupiedPlate"].replace("", "· liber ·")
        try:
            grid = sub.pivot(index="Level", columns="Leg", values="Cell")
            grid = grid.reindex(sorted(grid.index, key=int_key))
            grid = grid[sorted(grid.columns, key=int_key)]
            grid.index = [f"N{x}" for x in grid.index]
            grid.columns = [f"P{x}" for x in grid.columns]
            show_df(grid.reset_index(names=""), rename=False)
        except Exception:  # noqa: BLE001
            show_df(sub[["PositionCode", "OccupiedPlate"]])
        st.subheader("Poziții libere")
        fr = sort_positions(pv[~pv["Ocupat"]])
        show_df(fr[["PositionCode", "Flota"]].rename(columns={"PositionCode": "Poziție"}), rename=False)
    nop = hotel_df[(hotel_df["Status"] == ST_DEP) & (hotel_df["PositionCode"] == "")]
    if len(nop):
        st.subheader(f"Seturi fără poziție R-N-P ({len(nop)}) – pe locații vechi GY")
        lg = nop.assign(L=nop["LegacyLocation"].replace("", "(necompletat)")).groupby("L").size().reset_index(name="Seturi")
        show_df(lg.rename(columns={"L": "Locație veche GY"}), rename=False)

# --- 6. Rapoarte -----------------------------------------------------------
with tabs[6]:
    st.header("Rapoarte management")
    sets_df = build_sets(hotel_df, ty_df)
    over = sets_df[sets_df["Days"].notna() & (sets_df["Days"] > CFG["days"])].sort_values("Days", ascending=False)
    worn = sets_df[sets_df["MinTread"].notna() & (sets_df["MinTread"] < CFG["worn_mm"])]
    nopos = sets_df[sets_df["PositionCode"] == ""]
    odd = sets_df[(sets_df["Tyres"] != 4) | sets_df["Season"].str.contains("/")]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Seturi în hotel", len(sets_df))
    c2.metric("Anvelope", len(ty_df))
    c3.metric(f"Peste {CFG['days']} zile", len(over))
    c4.metric(f"Profil < {CFG['worn_mm']:g} mm", len(worn))
    c5.metric("Fără poziție R-N-P", len(nopos))
    cols_r = ["RegistrationNumber", "FleetName", "Phone", "PositionCode", "LegacyLocation", "Season", "Tyres",
              "Descriptions", "MinTread", "StorageDate", "Days"]
    st.subheader(f"⚠️ Facturare suplimentară (peste {CFG['days']} zile de la ultima depozitare/schimb)")
    if over.empty:
        st.success("Toate seturile se încadrează în termen.")
    else:
        show_df(over[cols_r])
        st.download_button("⬇️ Descarcă lista (CSV)", over[cols_r].to_csv(index=False).encode("utf-8-sig"),
                           "peste_termen.csv", "text/csv")
    st.subheader(f"🛞 Recomandări anvelope noi (cel puțin o anvelopă sub {CFG['worn_mm']:g} mm)")
    if worn.empty:
        st.success("Niciun set uzat în hotel.")
    else:
        show_df(worn[cols_r + ["DOTs"]])
        st.download_button("⬇️ Descarcă recomandările (CSV)", worn[cols_r].to_csv(index=False).encode("utf-8-sig"),
                           "recomandari_anvelope.csv", "text/csv")
    if len(odd):
        with st.expander(f"De verificat: seturi cu alt număr de anvelope decât 4 sau sezoane amestecate ({len(odd)})"):
            show_df(odd[cols_r])
    if len(nopos):
        with st.expander(f"Seturi fără poziție pe raft ({len(nopos)})"):
            show_df(nopos[cols_r])
    st.subheader("Export complet")
    ist_df = load(IST)
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ Seturi (CSV)", sets_df.to_csv(index=False).encode("utf-8-sig"), "seturi.csv", "text/csv")
    c2.download_button("⬇️ Hotel (CSV)", hotel_df.to_csv(index=False).encode("utf-8-sig"), "hotel.csv", "text/csv")
    c3.download_button("⬇️ Istoric (CSV)", ist_df.to_csv(index=False).encode("utf-8-sig"), "istoric.csv", "text/csv")
    with st.expander("Ultimele 100 de operațiuni"):
        show_df(ist_df.iloc[::-1].head(100))

# --- Fișe GY -------------------------------------------------------------------
with tabs[7]:
    st.header("Fișe GY (facturare)")
    st.caption("Flux: DE INTRODUS ÎN GY → TRIMIS LA GY → APROBAT GY → FACTURAT (sau RESPINS GY, cu notă). "
               "Se facturează doar după aprobarea GY.")
    fv = fise_df.copy()
    fv["Status"] = fv["Status"].str.strip().str.upper().replace("", F_TODO)
    cnt = fv["Status"].value_counts()
    cc_ = st.columns(len(F_STATUSES))
    for k, s_ in enumerate(F_STATUSES):
        cc_[k].metric(F_RO[s_], int(cnt.get(s_, 0)))
    if fv.empty:
        st.info("Nu există fișe GY. Ele se creează automat la montarea unui set de leasing și la introducerea în My Way.")
    else:
        hp = hotel_df.drop_duplicates("RegistrationNumber", keep="last").set_index(
            hotel_df.drop_duplicates("RegistrationNumber", keep="last")["RegistrationNumber"].map(norm_plate))
        rp = rec_df.set_index("ReceptionId")
        for k in CAR_PEOPLE:
            fv[k] = [rp.at[r, k] if r in rp.index and rp.at[r, k] else (hp.at[norm_plate(p), k] if norm_plate(p) in hp.index else "")
                     for r, p in zip(fv["ReceptionId"], fv["RegistrationNumber"])]
        g_st = st.radio("Status", F_STATUSES, horizontal=True, key="fg_status",
                        format_func=lambda s: f"{F_RO[s]} ({int(cnt.get(s, 0))})")
        sub = fv[fv["Status"] == g_st].sort_values("CreatedDate")
        if sub.empty:
            st.info("Nicio fișă cu acest status.")
        else:
            cols_f = ["FisaId", "RegistrationNumber", "FleetName", "UserName", "ClientCompany", "Type", "CreatedDate",
                      "SentDate", "ApprovedDate", "RejectedDate", "InvoicedDate", "GYRef", "Note"]
            ed = sub[cols_f].copy()
            ed.insert(0, "Selectează", False)
            ed = ed.rename(columns={c: DISPLAY.get(c, c) for c in cols_f})
            out = st.data_editor(ed, hide_index=True, key=f"fg_ed_{g_st}_{ver()}", width="stretch",
                                 disabled=[c for c in ed.columns if c != "Selectează"])
            chosen = sub["FisaId"][list(out["Selectează"].astype(bool))].tolist() if len(out) == len(sub) else []
            st.download_button("⬇️ Descarcă lista (CSV)", sub.to_csv(index=False).encode("utf-8-sig"),
                               f"fise_gy_{g_st.lower()}.csv", "text/csv")
            nexts = F_NEXT.get(g_st, [])
            if nexts:
                with st.form(f"fg_form_{g_st}"):
                    c1, c2, c3 = st.columns(3)
                    tgt = c1.selectbox("Mută în", nexts, format_func=lambda s: F_RO[s])
                    dt_f = c2.date_input("Data", value=date.today(), format="DD.MM.YYYY")
                    ref = c3.text_input("Nr. fișă GY (opțional)")
                    nt_f = st.text_input("Notă (obligatorie la RESPINS GY)")
                    all_f = st.checkbox(f"Aplică pe toate cele {len(sub)} fișe din listă (altfel doar cele bifate)")
                    ok_f = st.form_submit_button("➡️ Actualizează statusul", type="primary")
                if ok_f:
                    ids_f = sub["FisaId"].tolist() if all_f else chosen
                    if not ids_f:
                        st.error("Bifează cel puțin o fișă (coloana «Selectează») sau alege «toate».")
                    elif tgt == F_REJ and not nt_f.strip():
                        st.error("Scrie motivul respingerii în notă.")
                    else:
                        try:
                            d_, s_k = do_fisa_status(ids_f, tgt, dt_f, ref.strip(), nt_f.strip())
                            flash(f"✅ {d_} fișe mutate în {F_RO[tgt]}." + (f" {s_k} sărite." if s_k else ""))
                            st.rerun()
                        except Exception as e:  # noqa: BLE001
                            st.error(f"Eroare la actualizare: {e}")
            else:
                st.success("Fișe facturate – nu mai este nicio acțiune.")

# --- Sfârșit de sezon / My Way --------------------------------------------------
with tabs[8]:
    st.header("Sfârșit de sezon – My Way")
    st.caption(f"Seturi de leasing recepționate și nemontate. La inventarul de sfârșit de sezon (de obicei la maxim "
               f"{RC_DAYS} de zile de la recepție) se introduc în platforma My Way → EXTRA DEPOZITARE + fișă GY.")
    op_ = open_receptions(rec_df).copy()
    if op_.empty:
        st.success("Nu există seturi recepționate care așteaptă.")
    else:
        op_["Zile"] = op_.apply(lambda r: rec_age(r), axis=1)
        op_ = op_.sort_values("Zile", ascending=False, na_position="last")
        old_ = op_["Zile"].fillna(0) > RC_DAYS
        c1, c2 = st.columns(2)
        c1.metric("Seturi nemontate", len(op_))
        c2.metric(f"Peste {RC_DAYS} zile", int(old_.sum()))
        only_old = st.checkbox(f"Arată doar peste {RC_DAYS} zile", key="mw_only_old")
        pre = st.checkbox(f"Bifează automat seturile peste {RC_DAYS} zile", key="mw_pre")
        vw = op_[old_] if only_old else op_
        ed = pd.DataFrame({
            "Selectează": [bool(pre and (z or 0) > RC_DAYS) for z in vw["Zile"]],
            "": ["🔴" if (z or 0) > RC_DAYS else "" for z in vw["Zile"]],
            "Număr auto": vw["RegistrationNumber"], "VIN": vw["VIN"], "Stare": vw["Condition"], "Flotă": vw["FleetName"], "Utilizator": vw["UserName"],
            "Firmă client": vw["ClientCompany"], "Recepționat": vw["ReceptionDate"], "Zile": vw["Zile"],
            "Anvelope": vw["Tyres"], "Sezon": vw["Season"], "Locație așteptare": vw["WaitingLocation"],
            "Notă": vw["Note"]})
        out = st.data_editor(ed, hide_index=True, key=f"mw_ed_{only_old}_{pre}_{ver()}", width="stretch",
                             disabled=[c for c in ed.columns if c != "Selectează"])
        sel_ids = vw["ReceptionId"][list(out["Selectează"].astype(bool))].tolist() if len(out) == len(vw) else []
        st.download_button("⬇️ Descarcă lista (CSV)", vw.to_csv(index=False).encode("utf-8-sig"), "my_way.csv", "text/csv")
        nt_m = st.text_input("Notă (opțional)", key="mw_note")
        c1, c2 = st.columns(2)
        if c1.button(f"✅ Introdus în My Way – selectate ({len(sel_ids)})", type="primary", key="mw_bulk",
                     disabled=not sel_ids):
            n_m = do_myway(sel_ids, nt_m.strip())
            flash(f"✅ {n_m} seturi trecute pe EXTRA DEPOZITARE; fișele GY sunt în «De introdus în GY».")
            st.rerun()
        one = c2.selectbox("Sau un singur set", [""] + vw["ReceptionId"].tolist(), key="mw_one",
                           format_func=lambda x: "" if not x else
                           f"{vw.set_index('ReceptionId').at[x, 'RegistrationNumber'] or 'VIN ' + vw.set_index('ReceptionId').at[x, 'VIN']} ({vw.set_index('ReceptionId').at[x, 'ReceptionDate']})")
        if one and c2.button("✅ Introdus în My Way", key="mw_one_go"):
            n_m = do_myway([one], nt_m.strip())
            flash(f"✅ {n_m} set trecut pe EXTRA DEPOZITARE.")
            st.rerun()
    ex_ = rec_df[rec_df["Status"].str.upper() == RC_EXTRA]
    if len(ex_):
        with st.expander(f"Seturi în EXTRA DEPOZITARE ({len(ex_)})"):
            show_df(ex_[["RegistrationNumber", "FleetName", "UserName", "ClientCompany", "ReceptionDate", "MyWayDate",
                         "Tyres", "Season", "WaitingLocation", "Note"]])

# --- 7. Administrare poziții -----------------------------------------------
with tabs[9]:
    st.header("Administrare poziții")
    st.caption("Cod poziție: R(rând)-N(nivel)-P(picior), ex. R1-N1-P1. Rândurile pot fi dedicate unei flote sau COMUNE.")
    fleets_all = sorted(set(fleets_with_rows(pos_df)) | {f.strip() for f in hotel_df["FleetName"] if f.strip()})
    with st.form("gen_form"):
        st.markdown("**Generează poziții**")
        c1, c2, c3, c4 = st.columns(4)
        r_from = c1.number_input("De la rândul", 1, 999, 1)
        r_to = c2.number_input("Până la rândul", 1, 999, 1)
        levels = c3.number_input("Niveluri", 1, 20, 3)
        legs = c4.number_input("Picioare", 1, 50, 4)
        fsel = st.selectbox("Rândurile aparțin", [COMUN] + fleets_all + ["Flotă nouă…"])
        fnew = st.text_input("Nume flotă nouă (dacă ai ales «Flotă nouă…»)")
        upd = st.checkbox("Actualizează flota și pentru pozițiile deja existente din aceste rânduri")
        ok_g = st.form_submit_button("➕ Generează")
    if ok_g:
        fleet_g = fnew.strip() if fsel == "Flotă nouă…" else fsel
        if not fleet_g:
            st.error("Scrie numele flotei noi.")
        elif r_to < r_from:
            st.error("Rândul final trebuie să fie mai mare sau egal cu cel inițial.")
        else:
            try:
                a, u = do_generate_positions(int(r_from), int(r_to), int(levels), int(legs), fleet_g, upd)
                flash(f"✅ {a} poziții noi create, {u} actualizate (flota: {fleet_g}).")
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Eroare la generarea pozițiilor: {e}")

    if not pos_df.empty:
        rows_all = sorted(set(pos_df["Row"]), key=int_key)
        with st.form("assign_form"):
            st.markdown("**Alocă rânduri unei flote**")
            rs = st.multiselect("Rânduri", rows_all, format_func=lambda x: f"R{x}")
            fa = st.text_input("Flotă (scrie COMUN pentru rânduri comune)", value=COMUN)
            ok_a = st.form_submit_button("💾 Alocă")
        if ok_a:
            if not rs or not fa.strip():
                st.error("Alege rândurile și flota.")
            else:
                try:
                    n_a = do_assign_rows(rs, fa.strip())
                    flash(f"✅ {n_a} poziții alocate flotei {fa.strip()}.")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Eroare la alocare: {e}")
        with st.expander("Șterge pozițiile LIBERE dintr-un rând"):
            rd = st.selectbox("Rând", rows_all, format_func=lambda x: f"R{x}", key="del_row")
            if st.button("🗑️ Șterge pozițiile libere din rând"):
                try:
                    n_d = do_delete_free_in_row(rd)
                    flash(f"Am șters {n_d} poziții libere din R{rd}. Pozițiile ocupate au rămas.")
                    st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Eroare la ștergere: {e}")
        st.subheader("Toate pozițiile")
        show_df(sort_positions(sync_positions(hotel_df, pos_df)))

# --- 8. GY Fleet – import / export -----------------------------------------
with tabs[10]:
    st.header("GY Fleet – import și export")
    st.subheader("📥 Import export GY Fleet")
    st.caption("Încarcă fișierul exportat din GY Fleet (.xlsx sau .csv, aceleași 21 de coloane ca 'Inventar GY'). "
               "Potrivirea se face pe număr auto. Mașinile noi intră ca DEPOZITAT, fără poziție. Poziția, statusul "
               "și istoricul nu se modifică niciodată din import.")
    up = st.file_uploader("Fișier GY Fleet", type=["xlsx", "xlsm", "xls", "csv"], key="gy_file")
    apply_ch = st.checkbox("Înlocuiește și anvelopele mașinilor existente care diferă (atenție: anulează schimburile "
                           "făcute în aplicație după data exportului GY)", key="gy_apply_changes")
    if up is not None:
        plan = None
        try:
            imp_df, unknown, skipped = read_gy_file(up.name, up.getvalue())
            plan = plan_gy_import(hotel_df, ty_df, imp_df)
        except BackendError as e:
            st.error(str(e))
        except Exception as e:  # noqa: BLE001
            st.error(f"Eroare la citirea fișierului: {e}")
        if plan is not None:
            c1, c2, c3 = st.columns(3)
            c1.metric("Mașini noi", len(plan["new"]))
            c2.metric("Diferite", len(plan["changed"]))
            c3.metric("Neschimbate", plan["unchanged"])
            st.caption(f"{len(imp_df)} anvelope în fișier.")
            if unknown:
                st.caption("Coloane ignorate: " + ", ".join(unknown))
            if skipped:
                st.warning(f"{skipped} rânduri fără număr auto (ex. totaluri) au fost ignorate.")
            if plan["ridicat"]:
                st.warning("Mașini RIDICATE în aplicație care apar în GY (nu se importă): " + ", ".join(plan["ridicat"]))
            if plan["new"]:
                with st.expander(f"Mașini noi ({len(plan['new'])})", expanded=True):
                    show_df(imp_df[imp_df["RegistrationNumber"].isin(plan["new"])])
            if plan["changed"]:
                with st.expander(f"Mașini cu anvelope diferite ({len(plan['changed'])})", expanded=False):
                    for p in plan["changed"][:50]:
                        st.markdown(f"**{p}** – în aplicație: {describe(tyres_of(ty_df, p))}  \n"
                                    f"în fișier: {describe(imp_df[imp_df['RegistrationNumber'] == p])}")
            todo = len(plan["new"]) + (len(plan["changed"]) if apply_ch else 0)
            if todo:
                if st.button(f"✅ Confirmă importul ({todo} mașini)", type="primary", key="gy_confirm"):
                    try:
                        res, nd = do_gy_import(imp_df, apply_ch, f"Import GY Fleet: {up.name}")
                        flash(f"✅ Import finalizat: {nd} mașini importate/actualizate. Seturile noi nu au poziție; "
                              "o alegi la primul schimb.")
                        st.rerun()
                    except BackendError as e:
                        st.error(str(e))
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Eroare la import: {e}")
            else:
                st.success("Nimic de importat.")

    st.subheader("📤 Export în format GY Fleet")
    st.caption("Anvelopele aflate acum în hotel, câte un rând pe anvelopă, cu cele 21 de coloane GY în ordinea "
               "originală (CITY apare de două ori).")
    vals = gy_export_values(ty_df)
    st.caption(f"{len(vals) - 1} rânduri")
    stamp = date.today().strftime("%Y%m%d")
    c1, c2 = st.columns(2)
    try:
        c1.download_button("⬇️ Excel (.xlsx)", gy_export_xlsx(vals), f"hotel_gyfleet_{stamp}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="gy_xlsx")
    except Exception as e:  # noqa: BLE001
        c1.error(f"Nu pot genera fișierul Excel: {e}")
    c2.download_button("⬇️ CSV", gy_export_csv(vals), f"hotel_gyfleet_{stamp}.csv", "text/csv", key="gy_csv")
