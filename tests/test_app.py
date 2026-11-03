"""Teste pe date FICTIVE în formatul real GY Fleet (21 coloane, CITY de două ori, date m/d/yyyy, zecimale cu virgulă)."""
import csv as _csv
import hashlib
import io as _io
import os
import shutil
import tempfile
from datetime import date

import pandas as pd
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "streamlit_app.py")
TODAY_US = f"{date.today().month}/{date.today().day}/{date.today().year}"


def mk(tmp):
    os.environ["MADYT_DEMO"] = "1"
    os.environ["MADYT_DEMO_DIR"] = tmp
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    return at


def csv(tmp, n):
    return pd.read_csv(f"{tmp}/{n}.csv", dtype=str, keep_default_na=False)


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def errs(at):
    return [e.value for e in at.error]


def click(at, label):
    at.button[[b.label for b in at.button].index(label)].click().run()
    assert not at.exception, at.exception


def test_flow():
    tmp = tempfile.mkdtemp()
    at = mk(tmp)
    src = f"{tmp}/Inventar GY.csv"
    src_md5 = md5(src)
    assert len(at.tabs) == 11
    assert any("12 anvelope, 3 mașini" in i.value and "neatinsă" in i.value for i in at.info), [i.value for i in at.info]
    ty = csv(tmp, "Hotel_Anvelope")
    assert len(ty) == 12 and "CITY_2" in ty.columns and set(ty.CITY_2) == {"Buftea, Ilfov"}
    h = csv(tmp, "Hotel")
    assert len(h) == 3 and set(h.PositionCode) == {""} and h.set_index("RegistrationNumber").loc["B101DEM"].StorageDate == "2023-12-29"
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Seturi în hotel"] == "3" and metrics["Anvelope"] == "12", metrics
    assert metrics["Profil < 3 mm"] == "1"  # B102DEM are o anvelopă 2,5

    # SCHIMB SEZON – set comun, fără poziție -> se propune prima poziție a flotei
    at.text_input(key="swap_plate").set_value("b-101 dem").run()
    assert any("FĂRĂ POZIȚIE" in m.value and "Locație veche GY: D" in m.value for m in at.markdown)
    assert at.selectbox(key="swap_assign_B101DEM").value == "R1-N1-P1"
    assert at.radio(key="sw_B101DEM_season").value == "Summer"  # sezonul opus
    at.text_input(key="sw_B101DEM_brand").set_value("michelin")
    at.text_input(key="sw_B101DEM_desc").set_value("195/65R15 91H PRIMACY 4")
    at.text_input(key="sw_B101DEM_tread").set_value("5,5")
    at.text_input(key="sw_B101DEM_dot").set_value("0824")
    click(at, "✅ Confirmă schimbul")
    assert not errs(at), errs(at)
    ty = csv(tmp, "Hotel_Anvelope")
    b = ty[ty.RegistrationNumber == "B101DEM"]
    assert len(b) == 4 and set(b.BRAND) == {"MICHELIN"} and set(b.ProductGroup) == {"Summer"}
    assert set(b.TreadDepth) == {"5,5"} and set(b.DOT) == {"0824"} and set(b.StorageDate) == {TODAY_US}
    assert set(b["Chassis Num"]) == {"VF1DEMO0000000001"} and set(b["SOLD-TO"]) == {"0030000001"}
    assert set(b.CITY_2) == {"Buftea, Ilfov"} and set(b.ServiceProviderStorageLocation) == {"D"}
    arh = csv(tmp, "Arhiva_Anvelope")
    assert len(arh) == 4 and set(arh.ProductGroup) == {"Winter"} and arh.Reason.str.startswith("SCHIMB").all()
    hh = csv(tmp, "Hotel").set_index("RegistrationNumber").loc["B101DEM"]
    assert hh.PositionCode == "R1-N1-P1" and hh.StorageDate == date.today().isoformat() and hh.Season == "Summer"
    assert csv(tmp, "Pozitii").set_index("PositionCode").loc["R1-N1-P1"].OccupiedPlate == "B101DEM"
    ist = csv(tmp, "Istoric")
    assert ist.iloc[-1].Action == "SCHIMB" and "ULTRAGRIP" in ist.iloc[-1].Details and "PRIMACY" in ist.iloc[-1].Details

    # Al doilea schimb: aceeași poziție, 2 anvelope, profil uzat -> recomandare
    at = mk(tmp)
    at.text_input(key="swap_plate").set_value("B101DEM").run()
    assert any('class="pos-code">R1-N1-P1' in m.value for m in at.markdown)
    at.number_input(key="swap_n_B101DEM").set_value(2).run()
    at.text_input(key="sw_B101DEM_desc").set_value("185/65R15 88T ULTRAGRIP 9")
    at.text_input(key="sw_B101DEM_tread").set_value("2")
    click(at, "✅ Confirmă schimbul")
    ty = csv(tmp, "Hotel_Anvelope")
    assert (ty.RegistrationNumber == "B101DEM").sum() == 2
    assert "RECOMANDARE" in csv(tmp, "Istoric").iloc[-1].Details
    assert csv(tmp, "Hotel").set_index("RegistrationNumber").loc["B101DEM"].PositionCode == "R1-N1-P1"

    # RECEPȚIE flotă -> prima poziție liberă a flotei
    at = mk(tmp)
    at.selectbox(key="rec_type").set_value("Flotă: LEASING DEMO SRL").run()
    assert at.selectbox(key="rec_pos_LEASING DEMO SRL").value == "R1-N1-P2"
    [t for t in at.text_input if t.label == "Număr auto *"][0].set_value("cj99xyz")
    at.text_input(key="rec_brand").set_value("Pirelli")
    at.text_input(key="rec_desc").set_value("225/45R17 94V CINTURATO")
    at.text_input(key="rec_tread").set_value("7")
    click(at, "💾 Salvează recepția")
    assert not errs(at), errs(at)
    h = csv(tmp, "Hotel").set_index("RegistrationNumber")
    assert h.loc["CJ99XYZ"].PositionCode == "R1-N1-P2" and h.loc["CJ99XYZ"].Status == "DEPOZITAT"
    ty = csv(tmp, "Hotel_Anvelope")
    c = ty[ty.RegistrationNumber == "CJ99XYZ"]
    assert len(c) == 4 and set(c.TreadDepth) == {"7,0"} and set(c.ServiceProviderName) == {"MADYT Autoserv"}
    # recepție dublă refuzată
    at = mk(tmp)
    [t for t in at.text_input if t.label == "Număr auto *"][0].set_value("CJ99XYZ")
    [t for t in at.text_input if t.label == "Nume client *"][0].set_value("Ion")
    at.text_input(key="rec_desc").set_value("x")
    at.text_input(key="rec_tread").set_value("7")
    click(at, "💾 Salvează recepția")
    assert any("deja" in e for e in errs(at)), errs(at)

    # IEȘIRE
    at = mk(tmp)
    at.text_input(key="exit_plate").set_value("CJ99XYZ").run()
    next(c for c in at.checkbox if c.label.startswith("Confirm că setul a fost predat")).check()
    click(at, "🚪 Înregistrează ieșirea")
    h = csv(tmp, "Hotel").set_index("RegistrationNumber")
    assert h.loc["CJ99XYZ"].Status == "RIDICAT" and h.loc["CJ99XYZ"].ExitDate
    assert (csv(tmp, "Hotel_Anvelope").RegistrationNumber == "CJ99XYZ").sum() == 0
    assert csv(tmp, "Pozitii").set_index("PositionCode").loc["R1-N1-P2"].OccupiedPlate == ""
    assert csv(tmp, "Istoric").iloc[-1].Action == "IESIRE"

    # ADMIN – generare
    at = mk(tmp)
    nis = [n for n in at.number_input if n.label in ("De la rândul", "Până la rândul")]
    nis[0].set_value(4)
    nis[1].set_value(5)
    click(at, "➕ Generează")
    p = csv(tmp, "Pozitii")
    assert "R5-N3-P4" in set(p.PositionCode) and len(p) == 36 + 24
    assert md5(src) == src_md5, "Foaia sursă 'Inventar GY' NU trebuie modificată"
    shutil.rmtree(tmp)


def test_no_credentials():
    os.environ["MADYT_DEMO"] = "0"
    for k in ("MADYT_SA_FILE", "GOOGLE_APPLICATION_CREDENTIALS"):
        os.environ.pop(k, None)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception
    assert any("cheia contului de serviciu" in e.value for e in at.error), errs(at)


def _load_app(tmp):
    """Încarcă app.py în mod 'bare' (fără server) ca să testăm funcțiile direct."""
    import runpy
    import streamlit as st
    os.environ["MADYT_DEMO"] = "1"
    os.environ["MADYT_DEMO_DIR"] = tmp
    st.cache_data.clear()
    st.cache_resource.clear()
    return runpy.run_path(APP)


def test_leasing_ui_render():
    tmp = tempfile.mkdtemp()
    os.environ["MADYT_DEMO"] = "1"
    os.environ["MADYT_DEMO_DIR"] = tmp
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    m = {x.label: x.value for x in at.metric}
    assert m["Recepții leasing deschise"] == "0" and m["Fișe GY: De introdus în GY"] == "0", m
    for sec in ["📋 Lista recepțiilor", "✏️ Editează recepție", "📥 Import din Excel", "➕ Recepție nouă"]:
        at.radio(key="ls_section").set_value(sec).run()
        assert not at.exception, at.exception
    at.text_input(key="lr_plate").set_value("b 1 x").run()
    assert not at.exception


def test_leasing_ui_swap_myway_fise():
    tmp = tempfile.mkdtemp()
    at = mk(tmp)
    rc = csv(tmp, "Receptii")
    rows = []
    for rid, plate, d in (("RC1-B77TST", "B77TST", date.today().isoformat()), ("RC2-B88TST", "B88TST", "2026-01-05")):
        r = {c: "" for c in rc.columns}
        r.update({"ReceptionId": rid, "RegistrationNumber": plate, "FleetName": "HERTZ", "ReceptionDate": d, "Tyres": "4",
                  "Season": "Winter", "Status": "RECEPTIONAT", "UserName": "Ana", "ClientCompany": "ACME"})
        rows.append(r)
    pd.DataFrame(rows, columns=rc.columns).to_csv(f"{tmp}/Receptii.csv", index=False)
    rt = csv(tmp, "Receptii_Anvelope")
    pd.DataFrame([{**{c: "" for c in rt.columns}, "ReceptionId": "RC1-B77TST", "TyreNo": str(k), "RegistrationNumber": "B77TST",
                   "MaterialDescription": "205/55R16", "BRAND": "GOODYEAR", "ProductGroup": "Winter"} for k in range(1, 5)],
                 columns=rt.columns).to_csv(f"{tmp}/Receptii_Anvelope.csv", index=False)
    click(at, "🔄 Reîncarcă datele")
    m = {x.label: x.value for x in at.metric}
    assert m["Recepții leasing deschise"] == "2" and m["De introdus în My Way (>90 zile)"] == "1", m
    # montaj set recepționat (mașina nu e în hotel)
    at.text_input(key="swap_plate").set_value("b77tst").run()
    assert any("Set trimis de leasing" in s.value for s in at.subheader)
    assert not any("nu are niciun set" in w.value for w in at.warning)
    at.text_input(key="ls_B77TST_brand").set_value("michelin")
    at.text_input(key="ls_B77TST_desc").set_value("205/55R16 ALPIN")
    at.text_input(key="ls_B77TST_tread").set_value("6")
    click(at, "✅ Montat setul recepționat")
    assert not errs(at), errs(at)
    h = csv(tmp, "Hotel").set_index("RegistrationNumber").loc["B77TST"]
    assert h.Status == "DEPOZITAT" and h.UserName == "Ana" and h.ClientCompany == "ACME"
    assert csv(tmp, "Receptii").set_index("ReceptionId").loc["RC1-B77TST"].Status == "SCHIMBAT"
    # My Way pentru setul vechi
    at.selectbox(key="mw_one").set_value("RC2-B88TST").run()
    click(at, "✅ Introdus în My Way")
    assert csv(tmp, "Receptii").set_index("ReceptionId").loc["RC2-B88TST"].Status == "EXTRA_DEPOZITARE"
    f = csv(tmp, "Fise_GY")
    assert len(f) == 2 and set(f.Status) == {"DE_INTRODUS_GY"}
    # fișe GY: toate -> TRIMIS
    next(c for c in at.checkbox if c.label.startswith("Aplică pe toate")).check()
    click(at, "➡️ Actualizează statusul")
    assert not errs(at), errs(at)
    assert set(csv(tmp, "Fise_GY").Status) == {"TRIMIS_GY"}
    m = {x.label: x.value for x in at.metric}
    assert m["Fișe GY: Trimisă în GY"] == "2" and m["Recepții leasing deschise"] == "0", m


def test_vin_ui_card():
    tmp = tempfile.mkdtemp()
    at = mk(tmp)
    rc = csv(tmp, "Receptii")
    r = {c: "" for c in rc.columns}
    r.update({"ReceptionId": "RC1-VIN", "RegistrationNumber": "", "VIN": "WVWZZZ1KZAW654321", "Condition": "FOLOSITE",
              "FleetName": "ARVAL", "ReceptionDate": "2026-10-20", "Tyres": "4", "Season": "Winter",
              "Status": "RECEPTIONAT", "UserName": "Dan"})
    pd.DataFrame([r], columns=rc.columns).to_csv(f"{tmp}/Receptii.csv", index=False)
    click(at, "🔄 Reîncarcă datele")
    at.text_input(key="swap_plate").set_value("aw654321").run()
    assert not errs(at), errs(at)
    txt = " ".join(x.value for x in list(at.success) + list(at.info))
    assert "Are anvelope în hotel: NU" in txt and "Anvelope recepționate: DA" in txt and "FOLOSITE" in txt, txt
    at.text_input(key="swap_plate").set_value("").run()
    # căutare după număr existent în hotel (demo): DA în hotel, NU recepționate
    at.text_input(key="search_q").set_value("B101DEM").run()
    txt = " ".join(x.value for x in list(at.success) + list(at.info))
    assert "Are anvelope în hotel: DA" in txt and "Anvelope recepționate: NU" in txt, txt
    # legare VIN -> număr din fișă
    at.text_input(key="swap_plate").set_value("WVWZZZ1KZAW654321").run()
    fi = next(t for t in at.text_input if t.label.startswith("Număr auto pentru VIN"))
    fi.set_value("b 99 vin")
    click(at, "🔗 Leagă")
    assert not errs(at), errs(at)
    assert csv(tmp, "Receptii").RegistrationNumber[0] == "B99VIN"


def test_zz_functions_import_export():
    # rulează ULTIMUL: încărcarea "bare" a app.py lasă context Streamlit în proces
    tmp = tempfile.mkdtemp()
    mk(tmp)
    g = _load_app(tmp)
    # parsare format GY
    assert g["parse_date"]("12/29/2023").strftime("%Y-%m-%d") == "2023-12-29"
    assert g["parse_date"]("7/2/2026").strftime("%Y-%m-%d") == "2026-07-02"
    assert g["parse_date"]("15.10.2026").strftime("%Y-%m-%d") == "2026-10-15"
    assert g["parse_mm"]("5,0") == 5.0 and g["parse_mm"]("6/6/5/4") == 4.0 and g["fmt_mm"]("6") == "6,0"
    assert g["norm_season"]("WINTER") == "Winter" and g["norm_season"]("All Season") == "All Season"
    v = g["values_to_df"]([["A", "CITY", "CITY"], ["1", "x"], ["", "", ""]])
    assert list(v.columns) == ["A", "CITY", "CITY_2"] and len(v) == 1 and v.iloc[0].CITY_2 == ""

    # schimb pe fiecare anvelopă (valori goale = valoarea comună)
    common = {"BRAND": "FULDA", "MaterialDescription": "205/60R16 KRISTALL", "ProductGroup": "Winter",
              "WheelType": "Alloy", "TreadDepth": "6", "DOT": "3024", g["NOTE"]: ""}
    tyres = g["expand_tyres"](common, 3, [{"TreadDepth": "4,5"}, {"DOT": "1123", g["NOTE"]: "petic"}, {}])
    assert [t["TreadDepth"] for t in tyres] == ["4,5", "6", "6"] and tyres[1]["DOT"] == "1123"
    g["do_swap"]("XB203TST", tyres, "R2-N1-P1")
    ty = csv(tmp, "Hotel_Anvelope")
    x = ty[ty.RegistrationNumber == "XB203TST"]
    assert len(x) == 3 and list(x.TreadDepth) == ["4,5", "6,0", "6,0"] and list(x[g["NOTE"]]) == ["", "petic", ""]
    assert g["validate_tyres"]([{"MaterialDescription": "", "TreadDepth": "5"}])

    # EXPORT: 21 coloane, CITY de două ori, în ordinea GY
    vals = g["gy_export_values"](g["load"]("Hotel_Anvelope", fresh=True))
    assert len(vals[0]) == 21 and vals[0].count("CITY") == 2 and vals[0][2] == "CITY" and vals[0][9] == "CITY"
    xlsx = g["gy_export_xlsx"](vals)
    csvb = g["gy_export_csv"](vals)
    assert next(_csv.reader(_io.StringIO(csvb.decode("utf-8-sig")))) == vals[0]
    # Re-import al exportului -> nimic de schimbat
    hotel, tyd = g["load"]("Hotel", fresh=True), g["load"]("Hotel_Anvelope", fresh=True)
    for name, data in (("e.xlsx", xlsx), ("e.csv", csvb)):
        imp, unknown, skipped = g["read_gy_file"](name, data)
        assert list(imp.columns) == g["GY_COLS"] and set(imp.CITY_2) == {"Buftea, Ilfov"}, name
        plan = g["plan_gy_import"](hotel, tyd, imp)
        assert not plan["new"] and not plan["changed"] and plan["unchanged"] == 3, (name, plan)

    # IMPORT: fișier GY cu o mașină nouă, una modificată și un rând de totaluri
    rows = [r[:] for r in vals[1:]]
    for r in rows:
        if r[3] == "B102DEM":
            r[16] = "4,0"
    new = rows[0][:]
    new[1], new[3], new[15], new[12] = "LEASING NOU SRL", "b 999 new", "10/15/2026", "WINTER"
    rows += [new, new[:], [""] * 14 + ["1.079"]]
    buf = _io.StringIO()
    _csv.writer(buf).writerows([vals[0]] + rows)
    imp, _, skipped = g["read_gy_file"]("gy.csv", buf.getvalue().encode("cp1250"))
    assert skipped == 1
    plan = g["plan_gy_import"](hotel, tyd, imp)
    assert plan["new"] == ["B999NEW"] and plan["changed"] == ["B102DEM"], plan
    before = csv(tmp, "Hotel").set_index("RegistrationNumber")
    g["do_gy_import"](imp, False, "test")  # implicit: doar mașinile noi
    h = csv(tmp, "Hotel").set_index("RegistrationNumber")
    assert h.loc["B999NEW"].Status == "DEPOZITAT" and h.loc["B999NEW"].PositionCode == ""
    assert h.loc["B999NEW"].StorageDate == "2026-10-15" and h.loc["B999NEW"].Season == "Winter"
    ty = csv(tmp, "Hotel_Anvelope")
    assert (ty.RegistrationNumber == "B999NEW").sum() == 2
    assert "4,0" not in set(ty[ty.RegistrationNumber == "B102DEM"].TreadDepth)
    g["do_gy_import"](imp, True, "test")  # cu înlocuire
    ty = csv(tmp, "Hotel_Anvelope")
    assert set(ty[ty.RegistrationNumber == "B102DEM"].TreadDepth) == {"4,0"}
    h = csv(tmp, "Hotel").set_index("RegistrationNumber")
    assert h.loc["XB203TST"].PositionCode == before.loc["XB203TST"].PositionCode == "R2-N1-P1"
    assert (csv(tmp, "Istoric").Action == "IMPORT").sum() == 2
    shutil.rmtree(tmp)
