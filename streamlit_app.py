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
Sau, în modul DEMO, fișiere CSV locale cu aceleași nume.
"""
import csv
import io
import os
import re
from collections import Counter
from datetime import date, datetime

import pandas as pd
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
              "LegacyLocation", "Phone", "Email", "Note"]
POZ_COLS = ["PositionCode", "Row", "Level", "Leg", "FleetName", "OccupiedPlate"]
IST_COLS = ["Timestamp", "RegistrationNumber", "Action", "Details", "PositionCode", "UserNote", "Operator"]
ARH_COLS = ["ArchivedAt", "Reason"] + GY_COLS
SCHEMAS = {TY: GY_COLS, HOTEL: HOTEL_COLS, POZ: POZ_COLS, IST: IST_COLS, ARH: ARH_COLS}

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
        try:
            return self.sh.worksheet(name)
        except self._gs.exceptions.WorksheetNotFound:
            return None

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
        ws = self._ws(name)
        if ws is None:
            ws = self.sh.add_worksheet(title=name, rows=max(100, nrows + 20), cols=max(10, ncols))
        if ws.row_count < nrows or ws.col_count < ncols:
            ws.resize(rows=max(ws.row_count, nrows + 20), cols=max(ws.col_count, ncols))
        ws.update(range_name="A1", values=values, value_input_option="RAW")
        if ws.row_count > nrows:
            ws.batch_clear([f"A{nrows + 1}:{rowcol_to_a1(ws.row_count, ws.col_count)}"])

    def write(self, name, df):
        if name not in SCHEMAS or name == CFG["source_sheet"]:
            raise BackendError("Foaia sursă GY nu se modifică din aplicație.")
        self.write_values(name, [list(df.columns)] + df.astype(str).values.tolist())

    def append_many(self, name, rows, cols):
        if not rows:
            return
        ws = self._ws(name)
        if ws is None:
            ws = self.sh.add_worksheet(title=name, rows=100, cols=max(10, len(cols)))
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
    for name in (HOTEL, POZ, IST, ARH):
        if not be.exists(name):
            be.write(name, pd.DataFrame(columns=SCHEMAS[name]))
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
            "Phone": h["Phone"],
        })
    cols = ["RegistrationNumber", "FleetName", "PositionCode", "LegacyLocation", "Season", "Tyres", "Brands",
            "Descriptions", "MinTread", "DOTs", "Make/Model", "Chassis Num", "StorageDate", "Days", NOTE, "Phone"]
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
                "Phone": meta.get("Phone", ""), "Email": meta.get("Email", "")})
    j = find_row(hotel, plate)
    if j is not None:  # client vechi, RIDICAT -> refolosim rândul
        for k, v in rec.items():
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
        f"**Flotă / client:** {h['FleetName'] or '-'}  \n"
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


# --- conexiune ------------------------------------------------------------
st.title("🛞 MADYT – Hotel Anvelope")
try:
    init_msgs = initialize(CFG["demo"], CFG["spreadsheet_id"], CFG["demo_dir"])
    hotel_df = load(HOTEL)
    ty_df = load(TY)
    pos_df = load(POZ)
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

tabs = st.tabs(["🔁 Schimb sezon", "🔍 Căutare stoc", "📦 Recepție client nou", "🚪 Ieșire din hotel",
                "🗄️ Rafturi", "📊 Rapoarte", "⚙️ Administrare poziții", "🔄 GY Fleet"])

# --- 1. Schimb sezon --------------------------------------------------------
with tabs[0]:
    st.header("Schimb de sezon")
    plate = st.text_input("Număr auto", key="swap_plate", placeholder="ex: B123ABC").strip()
    if plate:
        np_ = norm_plate(plate)
        i = find_row(hotel_df, plate)
        if i is None:
            st.warning(f"Mașina {np_} nu are niciun set în hotel. Folosește tab-ul **Recepție client nou**.")
        elif hotel_df.at[i, "Status"] != ST_DEP:
            st.warning(f"Setul mașinii {np_} a fost RIDICAT pe {hotel_df.at[i, 'ExitDate'] or '-'}. "
                       "Pentru o nouă depozitare folosește tab-ul **Recepție client nou**.")
        else:
            h = hotel_df.loc[i]
            rows = tyres_of(ty_df, plate)
            st.subheader(f"🚗 {h['RegistrationNumber']}")
            pos_card(h["PositionCode"], legacy=h["LegacyLocation"])
            set_header(h, rows)
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

# --- 4. Ieșire din hotel ---------------------------------------------------
with tabs[3]:
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
with tabs[4]:
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
with tabs[5]:
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

# --- 7. Administrare poziții -----------------------------------------------
with tabs[6]:
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
with tabs[7]:
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
