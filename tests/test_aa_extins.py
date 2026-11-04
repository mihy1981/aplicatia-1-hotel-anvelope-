"""Funcțiile noi: tip facturare, mișcări, extra depozitare, comenzi, cereri relocare/casare (date DEMO inventate)."""
import os
import tempfile
from datetime import date

import pandas as pd
from streamlit.testing.v1 import AppTest

import extins as ex
from test_app import APP, click, csv, errs

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def mk_rich(tmp):
    os.environ["MADYT_DEMO"] = "1"
    os.environ["MADYT_DEMO_DIR"] = tmp
    os.environ["MADYT_DEMO_RICH"] = "1"
    try:
        at = AppTest.from_file(APP, default_timeout=120)
        at.run()
    finally:
        os.environ.pop("MADYT_DEMO_RICH", None)
    assert not at.exception, at.exception
    return at


def test_pure_logic():
    assert ex.default_type("ARVAL SERVICE LEASE ROMANIA SRL") == ex.BT_ARVAL
    assert ex.default_type("Autotehnica Fleet Services SRL") == ex.BT_HERTZ
    assert ex.default_type("ALTA FLOTA", ["ALTA FLOTA"]) == ex.BT_GY
    assert ex.default_type("") == ex.BT_NONE and ex.default_type("FIRMA X") == ex.BT_NONE
    assert ex.bill_via(ex.BT_HERTZ).startswith("MY") and ex.bill_via(ex.BT_PF) == "DIRECT"
    assert ex.norm_dim("205/65 R16 95H") == ex.norm_dim("205/65R16") == "2056516"
    lines = ex.parse_reception_paste("Furnizor Demo;F1;205/55 R16;4\nNecunoscut;F2;175/65R14;2")
    orders = pd.DataFrame([{"OrderId": "O1", "Status": ex.O_ORD, "Supplier": "Furnizor Demo SRL",
                            "Dimension": "205/55R16 91H", "Qty": "4"}])
    m, u = ex.match_receptions(lines, orders)
    assert [o for _, o in m] == ["O1"] and len(u) == 1
    a, b = ex.season_window("IARNA", 2026)
    assert a == date(2026, 10, 1) and b == date(2026, 12, 31)


def test_rich_demo_all_tabs_and_flows():
    tmp = tempfile.mkdtemp()
    at = mk_rich(tmp)
    assert len(at.tabs) == 18
    assert not errs(at), errs(at)
    cars = csv(tmp, "Masini").set_index("RegistrationNumber")
    assert cars.loc["B501AJD"].BillingType == ex.BT_HERTZ and cars.loc["B502AJD"].BillingType == ex.BT_PJ
    mv = csv(tmp, "Miscari")
    assert set(mv.Type) >= {ex.MV_IN, ex.MV_MOUNT, ex.MV_OUT_CAR, ex.MV_LEFT}
    left = mv[(mv.Type == ex.MV_LEFT) & (mv.RegistrationNumber == "B601ARV")].iloc[0]
    assert left.AWB == "3000000003" and left.State == ex.MST_OK
    rec = csv(tmp, "Receptii").set_index("RegistrationNumber")
    assert rec.loc["B601ARV"].Status == "PLECAT" and rec.loc["B601ARV"].LeftAWB == "3000000003"
    cmd = csv(tmp, "Comenzi")
    assert set(cmd.Status) >= {ex.O_OFFER, ex.O_ACC, ex.O_ORD, ex.O_SINV, ex.O_RCV, ex.O_TOBILL, ex.O_BILLED, ex.O_CANC}
    fac = csv(tmp, "Facturare")
    assert ((fac.Kind == "SCHIMB_SEZON") & (fac.RegistrationNumber == "B502AJD")).any()
    assert not ((fac.Kind == "SCHIMB_SEZON") & (fac.RegistrationNumber == "B501AJD")).any()  # leasing: nu direct
    # căutare: badge + istoric
    at.text_input(key="swap_plate").set_value("B502AJD").run()
    assert not at.exception, at.exception
    assert any("Client MADYT" in m.value or "AJ DEMO SRL" in m.value for m in at.markdown)
    # extra depozitare: (a) seturi fără schimb în sezon + (b) setul relocat
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.radio(key="fac_sec").set_value("🧾 Extra depozitare").run()
    assert not at.exception, at.exception
    click(at, next(b.label for b in at.button if b.label.startswith("🧾 Generează")))
    fac = csv(tmp, "Facturare")
    exl = fac[fac.Kind == "EXTRA_DEPOZITARE"]
    assert {"B601ARV", "XB203TST"} <= set(exl.RegistrationNumber)
    assert set(exl[exl.RegistrationNumber == "B601ARV"].Via) == {"MY_WAY / GY"}
    # a doua generare nu dublează
    at.run()
    assert not any(b.label.startswith("🧾 Generează") and not b.disabled for b in at.button)
    # cererea PROPUSĂ: setul rămâne până la aprobare
    h = csv(tmp, "Hotel").set_index("RegistrationNumber")
    assert h.loc["B101DEM"].Status == "DEPOZITAT"
    click(at, "✅ Confirmă (aprobat de Mihai)")
    h = csv(tmp, "Hotel").set_index("RegistrationNumber")
    assert h.loc["B101DEM"].Status == "RECICLAT"
    # toate secțiunile tab-urilor noi se randează fără excepții
    for key, opts in (("cls_sec", ["🚗 Mașini", "⚠️ Neclasificate", "👥 Clienți"]),
                      ("cmd_sec", ["📋 Comenzi", "➕ Ofertă nouă", "🚚 Comandate, nesosite încă", "📥 Recepții Beti (potrivire)"]),
                      ("fac_sec", ["💶 De facturat (client MADYT / PF)", "📊 Pe tip de facturare", "🏢 Pe client", "📚 Toate liniile"])):
        for o in opts:
            at.radio(key=key).set_value(o).run()
            assert not at.exception, (key, o, at.exception)
    at.radio(key="cmd_sec").set_value("📥 Recepții Beti (potrivire)").run()
    at.text_area(key="beti_txt").set_value("Furnizor Demo Anvelope;FDEMO-9;205/55 R16;4\nX;Y;100/10 R10;1").run()
    assert not at.exception, at.exception


def test_order_flow_ui():
    tmp = tempfile.mkdtemp()
    at = mk_rich(tmp)
    at.radio(key="cmd_sec").set_value("📋 Comenzi").run()
    cmd = csv(tmp, "Comenzi")
    oid = cmd[cmd.Status == ex.O_SINV].OrderId.iloc[0]
    at.selectbox(key="cmd_pick").set_value(oid).run()
    click(at, "⚠️ Problemă")
    assert any("Descrie problema" in e for e in errs(at))
    at.text_input(key=f"o_an_{oid}_{ex.O_SINV}").set_value("lipsă o anvelopă")
    click(at, "⚠️ Problemă")
    o = csv(tmp, "Comenzi").set_index("OrderId").loc[oid]
    assert o.Status == ex.O_RCV and o.ArrivalCheck == ex.ARR_PROBLEM and o.ArrivedAt
    click(at, "🔧 Montată pe mașină (→ de facturat)")
    o = csv(tmp, "Comenzi").set_index("OrderId").loc[oid]
    assert o.Status == ex.O_TOBILL
    fac = csv(tmp, "Facturare")
    assert (fac.Ref == f"CMD:{oid}").sum() == 1
