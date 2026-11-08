"""Run with: python -m pytest -q"""
from datetime import date

import pytest

import store
from evaluator import Comp, Settings, estimate, split_lot, stem

TODAY = date(2026, 11, 1)
COMPS = [
    Comp("Clear mount stamp set", "Stampin' Up", 14, date(2026, 10, 1)),
    Comp("Clear mount stamp set", "Stampin' Up", 16, date(2026, 9, 1)),
    Comp("Big Shot die cutting machine", "Stampin' Up", 55, date(2026, 8, 1)),
    Comp("Classic ink pad", "Stampin' Up", 6, date(2026, 8, 1)),
    Comp("Punch", "Stampin' Up", 10, date(2026, 8, 1)),
    Comp("12x12 strap-hinge album", "Creative Memories", 22, date(2026, 7, 1)),
    Comp("Old stamp set", "Stampin' Up", 99, date(2024, 1, 1)),  # outside comp window
]


def test_split_lot_quantities():
    assert split_lot("3 stamp sets, two albums & punches") == [(3, "stamp sets"), (2, "albums"), (1, "punches")]


def test_stemming():
    assert stem("punches") == "punch" and stem("memories") == "memory" and stem("sets") == "set"


def test_matching_and_window():
    est = estimate("4 Stampin Up stamp sets, big shot, punches, vintage buttons", COMPS, Settings(), TODAY)
    lines = {l.text: l for l in est.lines}
    assert lines["Stampin Up stamp sets"].unit_value == 15  # median of 14 and 16; the 2024 comp is excluded
    assert lines["big shot"].unit_value == 55
    assert lines["punches"].unit_value == 10
    assert lines["vintage buttons"].matches == []


def test_brand_words_alone_do_not_match():
    est = estimate("Stampin Up ribbon", COMPS, Settings(), TODAY)
    assert est.lines[0].matches == []


def test_wrong_brand_is_penalized():
    est = estimate("Creative Memories stamp set", COMPS, Settings(), TODAY)
    assert all(c.brand != "Stampin' Up" for _, c in est.lines[0].matches)


def test_max_bid_hits_target_multiple():
    s = Settings(buyer_premium_pct=15, lot_shipping=10, sales_tax_pct=7, target_multiple=3)
    est = estimate("10 Stampin Up stamp sets", COMPS, s, TODAY)
    bid = est.max_bid
    assert bid > 0
    assert est.net_proceeds == pytest.approx(3 * est.total_cost(bid))
    # gross 150; fees 150*.1325 + 10*.40 = 23.875; ship 65 -> net 61.125
    assert est.net_proceeds == pytest.approx(61.125)


def test_monthly_report(tmp_path):
    con = store.connect(tmp_path / "t.db")
    s = Settings(buyer_premium_pct=10)
    lot = store.add_lot(con, "2026-01-15", "x", "lot", 100, s)  # cost 110
    store.add_sale(con, lot, "2026-02-03", "item", 200, 10, 8, 30)
    rows = {r["month"]: r for r in store.monthly_report(con)}
    assert rows["2026-01"]["profit"] == pytest.approx(-110)
    assert rows["2026-02"]["profit"] == pytest.approx(200 + 10 - 30 - 8)
    assert store.lot_report(con)[0]["profit"] == pytest.approx(172 - 110)
