"""Recepții leasing, montaj, My Way, fișe GY și import Excel – pe date DEMO."""
import importlib.util
import io
import os
import sys
import tempfile

import pandas as pd
from streamlit.testing.v1 import AppTest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
APP = os.path.join(ROOT, "streamlit_app.py")
sys.path.insert(0, ROOT)
import receptii_import as rimp  # noqa: E402


def load_app(tmp):
    os.environ["MADYT_DEMO"] = "1"
    os.environ["MADYT_DEMO_DIR"] = tmp
    spec = importlib.util.spec_from_file_location(f"app_{os.path.basename(tmp)}", APP)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # rulează în „bare mode”; ne interesează funcțiile
    m.clear_cache()
    return m


def csv(tmp, n):
    return pd.read_csv(f"{tmp}/{n}.csv", dtype=str, keep_default_na=False)


def tyres(n=4, **kw):
    t = {"MaterialDescription": "205/55R16 91H", "BRAND": "goodyear", "TyreModel": "ultragrip 9+",
         "ProductGroup": "IARNA", "DOT": "3525", "TreadDepth": "8", "Axle": "", "Note": ""}
    t.update(kw)
    return [dict(t) for _ in range(n)]


def test_leasing_flow():
    tmp = tempfile.mkdtemp()
    m = load_app(tmp)
    assert "UserName" in csv(tmp, "Hotel").columns and "ClientCompany" in csv(tmp, "Hotel").columns
    for t in ("Receptii", "Receptii_Anvelope", "Fise_GY"):
        assert os.path.exists(f"{tmp}/{t}.csv")
    assert "HERTZ" in m.all_fleets()

    rid = m.do_leasing_reception({"RegistrationNumber": "b 55 tst", "FleetName": "HERTZ", "UserName": "Ion Pop",
                                  "ClientCompany": "ACME SRL"}, tyres() + [{"MaterialDescription": ""}])
    rec = csv(tmp, "Receptii")
    assert len(rec) == 1 and rec.Status[0] == "RECEPTIONAT" and rec.RegistrationNumber[0] == "B55TST"
    assert rec.Tyres[0] == "4" and rec.Season[0] == "Winter" and rec.ClientCompany[0] == "ACME SRL"
    rty = csv(tmp, "Receptii_Anvelope")
    assert len(rty) == 4 and set(rty.ReceptionId) == {rid} and set(rty.BRAND) == {"GOODYEAR"}
    # dublură blocată fără confirmare
    try:
        m.do_leasing_reception({"RegistrationNumber": "B55TST", "FleetName": "HERTZ"}, tyres())
        raise AssertionError("trebuia blocat")
    except m.BackendError as e:
        assert "deja" in str(e)

    # editare: o anvelopă modificată + una adăugată
    t2 = tyres()
    t2[0]["TreadDepth"] = "7,5"
    t2.append(dict(t2[1], Axle="REZERVĂ"))
    assert m.do_edit_reception(rid, {"WaitingLocation": "container 2", "UserPhone": "0722"}, t2) >= 3
    rty = csv(tmp, "Receptii_Anvelope")
    assert len(rty) == 5 and rty.TreadDepth[rty.TyreNo == "1"].iloc[0] == "7,5"
    ist = csv(tmp, "Istoric")
    assert (ist.Action == "EDITARE_RECEPTIE").sum() == 1 and "container 2" in ist.Details.iloc[-1]

    # montaj: mașina nu are set DEPOZITAT -> setul dat jos intră pe raft, fișă GY
    m.do_generate_positions(1, 1, 1, 2, "COMUN", False)
    code, worn = m.do_leasing_swap(rid, tyres(4, BRAND="Michelin", ProductGroup="Summer", TreadDepth="2,5",
                                              WheelType="Tyre Only"), "R1-N1-P1")
    assert code == "R1-N1-P1" and worn == 4
    h = csv(tmp, "Hotel").set_index("RegistrationNumber").loc["B55TST"]
    assert h.Status == "DECIZIE_GY_ASTEPTATA" and h.FleetName == "HERTZ" and h.UserName == "Ion Pop" and h.UserPhone == "0722"
    ty = csv(tmp, "Hotel_Anvelope")
    assert (ty.RegistrationNumber == "B55TST").sum() == 4
    rec = csv(tmp, "Receptii")
    assert rec.Status[0] == "SCHIMBAT" and rec.SwapDate[0]
    f = csv(tmp, "Fise_GY")
    assert len(f) == 1 and f.Status[0] == "DE_INTRODUS_GY" and f.Type[0] == "SCHIMB (MONTAJ SET LEASING)"

    # fișa: tranziții permise / nepermise
    fid = f.FisaId[0]
    assert m.do_fisa_status([fid], "FACTURAT") == (0, 1)
    assert m.do_fisa_status([fid], "TRIMIS_GY", gy_ref="GY123") == (1, 0)
    assert m.do_fisa_status([fid], "RESPINS_GY", note="lipsă poze") == (1, 0)
    assert m.do_fisa_status([fid], "TRIMIS_GY") == (1, 0)
    assert m.do_fisa_status([fid], "APROBAT_GY") == (1, 0)
    assert m.do_fisa_status([fid], "FACTURAT") == (1, 0)
    f = csv(tmp, "Fise_GY").iloc[0]
    assert f.Status == "FACTURAT" and f.SentDate and f.ApprovedDate and f.RejectedDate and f.InvoicedDate
    assert f.GYRef == "GY123" and "lipsă poze" in f.Note

    # a doua mașină: nu vine -> My Way
    rid2 = m.do_leasing_reception({"RegistrationNumber": "CJ01TST", "FleetName": "ARVAL SERVICE LEASE ROMANIA SRL",
                                   "ReceptionDate": "2026-01-10"}, tyres())
    assert m.do_myway([rid2, "inexistent"]) == 1
    rec = csv(tmp, "Receptii").set_index("ReceptionId").loc[rid2]
    assert rec.Status == "EXTRA_DEPOZITARE" and rec.MyWayDate
    f = csv(tmp, "Fise_GY")
    assert (f.Type == "EXTRA DEPOZITARE").sum() == 1

    # car people editabile
    assert m.do_edit_car_people("B55TST", {"UserName": "Ion Popescu", "UserPhone": "", "ClientCompany": "ACME"}) == 3


def test_import_module():
    df = pd.DataFrame({
        "RegistrationNumber": ["B 11 AAA"] * 4 + ["B22BBB"] * 2 + [""],
        "FleetName": ["HERTZ"] * 6 + [""],
        "MaterialDescription": ["205/55R16 91H"] * 6 + [""],
        "BRAND": ["Goodyear"] * 6 + [""],
        "ProductGroup": ["Winter"] * 4 + ["Summer", "Winter"] + [""],
        "DOT": ["3525"] * 6 + [""], "TreadDepth": ["8"] * 6 + ["Total"],
        "ServiceProviderStorageLocation": ["DF", "SF", "DS", "SS", "", ""] + [""],
    })
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    raw = rimp.read_file("x.xlsx", buf.getvalue())
    mp = rimp.auto_map(raw.columns)
    assert mp["RegistrationNumber"] == "RegistrationNumber" and mp["Axle"] == "ServiceProviderStorageLocation"
    recs, warns, skipped = rimp.build_plan(raw, mp, open_plates={"B22BBB"})
    assert [r["RegistrationNumber"] for r in recs] == ["B11AAA", "B22BBB"] and skipped == 1
    assert [t["Axle"] for t in recs[0]["tyres"]] == ["FD", "FS", "SD", "SS"]
    assert any("B22BBB" in w and "deschisă" in w for w in warns) and any("sezoane" in w for w in warns)
    raw2 = rimp.read_file("x.csv", "Nr auto;Dimensiune;Marca\nB33CCC;195/65R15;Michelin\n".encode())
    mp2 = rimp.auto_map(raw2.columns)
    assert mp2 == {"RegistrationNumber": "Nr auto", "MaterialDescription": "Dimensiune", "BRAND": "Marca"}


def test_vin_flow():
    tmp = tempfile.mkdtemp()
    m = load_app(tmp)
    assert "VIN" in csv(tmp, "Hotel").columns and {"VIN", "Condition"} <= set(csv(tmp, "Receptii").columns)
    vin = "WVWZZZ1KZAW123456"
    # recepție doar cu VIN, anvelope folosite
    rid = m.do_leasing_reception({"RegistrationNumber": "", "VIN": "wvw-zzz1kzaw123456", "Condition": "folosite",
                                  "FleetName": "ARVAL"}, tyres())
    r = csv(tmp, "Receptii").iloc[0]
    assert r.RegistrationNumber == "" and r.VIN == vin and r.Condition == "FOLOSITE"
    try:
        m.do_leasing_reception({"VIN": "123"}, tyres())
        raise AssertionError("VIN scurt trebuia refuzat")
    except m.BackendError:
        pass
    try:  # aceeași mașină (după VIN) -> dublură
        m.do_leasing_reception({"VIN": vin, "FleetName": "ARVAL"}, tyres())
        raise AssertionError("dublură VIN")
    except m.BackendError as e:
        assert "deja" in str(e)
    res = m.resolve_car("aw123456")
    assert res["by"] == "vin" and res["vins"] == [vin] and res["plates"] == []
    assert len(m.receptions_for(m.load(m.REC), "", res["vins"], only_open=True)) == 1
    try:  # montaj imposibil fără număr
        m.do_leasing_swap(rid, tyres(4, ProductGroup="Summer", TreadDepth="3"), "")
        raise AssertionError("trebuia cerută legarea")
    except m.BackendError as e:
        assert "Leag" in str(e)
    # legare de număr, apoi montaj -> VIN pe mașină în Hotel
    assert m.do_link_reception(rid, "b 77 vin") == "B77VIN"
    assert set(csv(tmp, "Receptii_Anvelope").RegistrationNumber) == {"B77VIN"}
    assert (csv(tmp, "Istoric").Action == "LEGARE_RECEPTIE").sum() == 1
    m.do_leasing_swap(rid, tyres(4, ProductGroup="Summer", TreadDepth="3"), "")
    h = csv(tmp, "Hotel").set_index("RegistrationNumber").loc["B77VIN"]
    assert h.VIN == vin and h.Status == "DECIZIE_GY_ASTEPTATA"
    res = m.resolve_car("ZAW123456")
    assert res["plates"] == ["B77VIN"] and vin in res["vins"]
    assert m.resolve_car("B77VIN")["by"] == "plate"
    assert m.resolve_car("nimic")["by"] == ""
    # VIN preluat din Hotel_Anvelope (Chassis Num) pentru o mașină fără VIN în Hotel
    m.do_reception({"RegistrationNumber": "B88CHS", "FleetName": "X", "Chassis Num": "VF1RFB00123987654"},
                   tyres(4, ProductGroup="Summer"), "")
    assert m.resolve_car("987654")["plates"] == ["B88CHS"]
    assert m.do_edit_car_people("B88CHS", {"VIN": "VF1RFB00123987654"}) == 0


def test_import_vin():
    raw = rimp.read_file("x.csv", ("Serie sasiu;Nr auto;Dimensiune;Stare\n"
                                   + "WVWZZZ1KZAW111111;;205/55R16;folosite\n" * 4
                                   + ";B1XYZ;205/55R16;\n").encode())
    mp = rimp.auto_map(raw.columns)
    assert mp["VIN"] == "Serie sasiu" and mp["Condition"] == "Stare"
    assert not rimp.missing_required(mp)
    recs, warns, _ = rimp.build_plan(raw, mp, open_vins={"WVWZZZ1KZAW111111"})
    assert recs[0]["VIN"] == "WVWZZZ1KZAW111111" and recs[0]["RegistrationNumber"] == ""
    assert recs[0]["Condition"] == "FOLOSITE" and recs[1]["Condition"] == "NOI"
    assert any("deschisă" in w for w in warns)
    tmp = tempfile.mkdtemp()
    m = load_app(tmp)
    created, skipped = m.do_bulk_leasing_reception(recs, "2026-11-01", "", True, "test")
    assert skipped == [] and len(created) == 2
    rec = csv(tmp, "Receptii")
    assert set(rec.Condition) == {"NOI", "FOLOSITE"} and "WVWZZZ1KZAW111111" in set(rec.VIN)


def test_gy_decision_and_notices():
    tmp = tempfile.mkdtemp()
    m = load_app(tmp)
    m.do_generate_positions(1, 1, 1, 4, "COMUN", False)
    # --- decizia GY după montaj
    rid = m.do_leasing_reception({"RegistrationNumber": "B10GYQ", "FleetName": "HERTZ", "VIN": "WVWZZZ1KZAW000001"},
                                 tyres())
    m.do_leasing_swap(rid, tyres(4, BRAND="Michelin", ProductGroup="Summer", TreadDepth="5", WheelType="Tyre Only",
                                 DOT="1222"), "R1-N1-P1")
    h = m.load(m.HOTEL, fresh=True)
    q = h[h.Status == "DECIZIE_GY_ASTEPTATA"]
    assert list(q.RegistrationNumber) == ["B10GYQ"] and q.GYAskedDate.iloc[0]
    assert m.occupied_map(h).get("R1-N1-P1") == "B10GYQ"  # poziția rămâne ocupată
    txt = m.gy_email_text(q.iloc[0], m.tyres_of(m.load(m.TY, fresh=True), "B10GYQ"))
    assert "B10GYQ" in txt and "WVWZZZ1KZAW000001" in txt and "DOT 1222" in txt and "205/55R16" in txt
    assert "MICHELIN" in txt.upper() and "5,0 mm" in txt and "PĂSTRĂM" in txt
    assert m.do_gy_decision(["B10GYQ"], "PASTRAM", "2026-01-15", note="email GY") == 1
    h = m.load(m.HOTEL, fresh=True).set_index("RegistrationNumber").loc["B10GYQ"]
    assert h.Status == "DEPOZITAT" and h.BillingStart == "2026-01-15" and h.BillingEnd == "2026-07-15"
    f = csv(tmp, "Fise_GY")
    s6 = f[f.Type == "DEPOZITARE 6 LUNI"]
    assert len(s6) == 1 and s6.Status.iloc[0] == "DE_INTRODUS_GY" and s6.PeriodEnd.iloc[0] == "2026-07-15"
    # perioada expirată -> refacturare
    assert list(m.storage_expired(m.load(m.HOTEL, fresh=True)).RegistrationNumber) == ["B10GYQ"]
    assert m.do_rebill(["B10GYQ"]) == 1
    f = csv(tmp, "Fise_GY")
    assert (f.Type == "DEPOZITARE 6 LUNI").sum() == 2 and "2026-07-15" in set(f.PeriodStart)
    # reciclare
    rid2 = m.do_leasing_reception({"RegistrationNumber": "B11GYQ", "FleetName": "HERTZ"}, tyres())
    m.do_leasing_swap(rid2, tyres(4, ProductGroup="Summer", TreadDepth="2", WheelType="Tyre Only"), "R1-N1-P2")
    assert m.do_gy_decision(["B11GYQ"], "RECICLAM", billable=True) == 1
    h = m.load(m.HOTEL, fresh=True).set_index("RegistrationNumber").loc["B11GYQ"]
    assert h.Status == "RECICLAT" and h.GYDecision == "RECICLAT"
    assert "R1-N1-P2" not in m.occupied_map(m.load(m.HOTEL, fresh=True))
    assert (csv(tmp, "Hotel_Anvelope").RegistrationNumber == "B11GYQ").sum() == 0
    assert csv(tmp, "Arhiva_Anvelope").Reason.str.contains("RECICLARE").sum() == 4
    f = csv(tmp, "Fise_GY")
    fr = f[f.Type == "RECICLARE"]
    assert len(fr) == 1 and fr.Billable.iloc[0] == "DA"
    m.do_fisa_billable(fr.FisaId.iloc[0], False)
    assert csv(tmp, "Fise_GY").set_index("FisaId").at[fr.FisaId.iloc[0], "Billable"] == "NU"

    # --- anunțuri curier: anunțul nu e sosire; recepția îl închide
    items = [
        {"date": "2026-10-20 10:00", "subject": "s1", "kind": "VIN (primiți)", "id": "B20NOT", "id_type": "nr",
         "awb": "7000000000001", "qty": 4, "season": ["Winter"], "desc": ["195/65R15 91T ESKIMO S3+ MS"],
         "from": "HIL SERV", "courier": "FAN Courier"},
        {"date": "2026-10-21 10:00", "subject": "s2", "kind": "VIN (primiți)", "id": "YARVNFC35RZ999999",
         "id_type": "VIN", "awb": "7000000000002", "qty": 4, "season": ["Winter"], "desc": ["205/75R16C 113R CW51"]},
        {"date": "2026-10-22", "subject": "s3", "kind": "VIN (primiți)", "id": "B21NOT", "awb": "7000000000003",
         "qty": 4, "season": ["Winter"], "desc": ["x"]},
        {"date": "2026-10-23", "subject": "s3b", "kind": "ANULARE", "id": "B21NOT", "awb": "7000000000003"},
        {"date": "2026-10-24", "subject": "s4", "kind": "PLEACĂ (pregătiți pentru ridicare FAN Courier)",
         "id": "B22OUT", "awb": "7000000000004", "qty": 4, "season": ["Winter"], "desc": ["y"], "to": "NESTE"},
    ]
    rows, skipped = rimp.notices_from_interspace(items)
    assert len(rows) == 3 and skipped == ["7000000000003"]
    assert [r["Status"] for r in rows] == ["ANUNTAT", "ANUNTAT", "DE_PREDAT"]
    assert rows[1]["VIN"] == "YARVNFC35RZ999999" and rows[1]["RegistrationNumber"] == ""
    assert rimp.notices_from_interspace(items, [r["AWB"] for r in rows])[0] == []
    m.backend().append_many(m.NOT, [[r[c] for c in m.NOT_COLS] for r in rows], m.NOT_COLS)
    tt = rimp.notice_tyres(rows[0])
    assert len(tt) == 4 and tt[0]["BRAND"] == "SAVA" and tt[0]["ProductGroup"] == "Winter"
    # recepție datată ÎNAINTE de anunț -> nu închide anunțul
    m.do_leasing_reception({"RegistrationNumber": "B20NOT", "ReceptionDate": "2026-10-12"}, tyres())
    nt = csv(tmp, "Anunturi_Curier").set_index("AWB")
    assert nt.at["7000000000001", "Status"] == "ANUNTAT"
    # import (bulk) cu VIN după anunț -> închis automat, cu discrepanță la cantitate
    created, _ = m.do_bulk_leasing_reception([{"RegistrationNumber": "", "VIN": "YARVNFC35RZ999999",
                                               "FleetName": "HERTZ", "tyres": tyres(2)}], "2026-10-25")
    nt = csv(tmp, "Anunturi_Curier").set_index("AWB")
    assert nt.at["7000000000002", "Status"] == "RECEPTIONAT" and "DISCREPANȚĂ" in nt.at["7000000000002", "Note"]
    rec = csv(tmp, "Receptii")
    assert rec[rec.VIN == "YARVNFC35RZ999999"].AWB.iloc[0] == "7000000000002"
    # confirmare explicită din listă (NoticeId) pentru B20NOT
    nid = nt.at["7000000000001", "NoticeId"]
    m.do_leasing_reception({"RegistrationNumber": "B20NOT", "ReceptionDate": "2026-10-26", "NoticeId": nid,
                            "AWB": "7000000000001"}, tt, allow_duplicate=True)
    nt = csv(tmp, "Anunturi_Curier").set_index("AWB")
    assert nt.at["7000000000001", "Status"] == "RECEPTIONAT" and nt.at["7000000000001", "ReceptionId"]
    # predare la curier
    m.do_notice_status(nt.at["7000000000004", "NoticeId"], "PREDAT", "2026-10-27", "predat")
    nt = csv(tmp, "Anunturi_Curier").set_index("AWB")
    assert nt.at["7000000000004", "Status"] == "PREDAT" and nt.at["7000000000004", "ClosedDate"] == "2026-10-27"
    try:
        m.do_notice_status(nt.at["7000000000004", "NoticeId"], "PREDAT")
        raise AssertionError("dublă predare")
    except m.BackendError:
        pass


def test_enrich():
    hotel = pd.DataFrame({"RegistrationNumber": ["B1AAA"], "FleetName": ["HERTZ"], "Status": ["DEPOZITAT"],
                          "VIN": [""]})
    ty = pd.DataFrame({"RegistrationNumber": ["B1AAA"], "FleetName": ["HERTZ"], "Chassis Num": ["VF1MB000172828387"],
                       "MaterialDescription": ["195/75R16C 107R X"]})
    old = pd.DataFrame({"RegistrationNumber": ["AG061763/B2BBB", "", "B2BBB Count"],
                        "wms": ["", "B3CCC", ""], "FleetName": ["Autotehnica", "Autotehnica", ""],
                        "Fleet VIN": ["", "AHTBB3CD201789378", ""], "ProductGroup": ["", "265/60R18 114H WS71", ""],
                        "Chassis Num": ["VF1VB000472918766", "", ""]})
    idx = rimp.ref_index([("Hotel", hotel), ("Hotel_Anvelope", ty), ("old", old)])
    assert idx["B1AAA"]["VIN"] == "VF1MB000172828387" and idx["B1AAA"]["FleetName"] == "HERTZ"
    assert idx["B2BBB"]["VIN"] == "VF1VB000472918766" and "AG061763" in idx["B2BBB"]["aliases"]
    assert idx["B3CCC"]["VIN"] == "AHTBB3CD201789378" and idx["B3CCC"]["FleetName"] == "Autotehnica"
    recs = [{"RegistrationNumber": "B1AAA", "VIN": "", "FleetName": "", "tyres": [{"MaterialDescription": "205/55R16 91H"}]},
            {"RegistrationNumber": "B9ZZZ", "VIN": "", "FleetName": "", "tyres": [{"MaterialDescription": "205/55R16"}]}]
    rep = rimp.enrich_plan(recs, idx)
    assert recs[0]["FleetName"] == "HERTZ" and recs[0]["VIN"] == "VF1MB000172828387"
    assert "dimensiune diferită" in rep[0]["Observații"] and "necunoscută" in rep[1]["Observații"]


PREP = r"""
import os, sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, os.path.join(sys.argv[1], "tests"))
from test_leasing import load_app, tyres, rimp
m = load_app(sys.argv[2])
m.do_generate_positions(1, 1, 1, 2, "COMUN", False)
rid = m.do_leasing_reception({"RegistrationNumber": "B10GYQ", "FleetName": "HERTZ"}, tyres())
m.do_leasing_swap(rid, tyres(4, ProductGroup="Summer", WheelType="Tyre Only"), "R1-N1-P1")
rows, _ = rimp.notices_from_interspace([
    {"date": "2026-10-20", "kind": "VIN (primiți)", "id": "B20NOT", "awb": "7000000000001", "qty": 4,
     "season": ["Winter"], "desc": ["195/65R15 91T ESKIMO S3+ MS"]},
    {"date": "2026-10-24", "kind": "PLEACĂ", "id": "B22OUT", "awb": "7000000000004", "qty": 4}])
m.backend().append_many(m.NOT, [[r[c] for c in m.NOT_COLS] for r in rows], m.NOT_COLS)
"""


def test_render_gy_and_courier_tabs():
    import subprocess
    tmp = tempfile.mkdtemp()
    # datele se pregătesc într-un proces separat (modul „bare” al aplicației nu se amestecă cu AppTest)
    subprocess.run([sys.executable, "-c", PREP, ROOT, tmp], check=True, capture_output=True,
                   env=dict(os.environ, MADYT_DEMO="1", MADYT_DEMO_DIR=tmp))
    # AppTest tot într-un proces curat (după modul „bare” rămâne un context st.form agățat)
    out = subprocess.run([sys.executable, "-c", RENDER, APP], capture_output=True, text=True,
                         env=dict(os.environ, MADYT_DEMO="1", MADYT_DEMO_DIR=tmp))
    assert out.returncode == 0, out.stderr[-3000:]
    assert "RENDER_OK" in out.stdout, out.stdout[-2000:]


RENDER = r"""
import sys
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(sys.argv[1], default_timeout=60)
at.run()
assert not at.exception, at.exception
labels = [t.label for t in at.tabs]
assert any("Curier" in x for x in labels) and any("De întrebat GY" in x for x in labels)
gy = at.tabs[[i for i, x in enumerate(labels) if "De întrebat GY" in x][0]]
assert any("B10GYQ" in c.value for c in gy.code)
vals = {mm.label: mm.value for mm in at.metric}
assert vals.get("De întrebat GY (set demontat)") == "1", vals
assert vals.get("Sosiri anunțate curier (în drum)") == "1", vals
assert vals.get("De predat curierului") == "1", vals
print("RENDER_OK")
"""
