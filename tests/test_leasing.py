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
    assert h.Status == "DEPOZITAT" and h.FleetName == "HERTZ" and h.UserName == "Ion Pop" and h.UserPhone == "0722"
    ty = csv(tmp, "Hotel_Anvelope")
    assert (ty.RegistrationNumber == "B55TST").sum() == 4
    rec = csv(tmp, "Receptii")
    assert rec.Status[0] == "SCHIMBAT" and rec.SwapDate[0]
    f = csv(tmp, "Fise_GY")
    assert len(f) == 1 and f.Status[0] == "DE_INTRODUS_GY" and f.Type[0] == "SCHIMB + DEPOZITARE"

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
    assert h.VIN == vin and h.Status == "DEPOZITAT"
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
