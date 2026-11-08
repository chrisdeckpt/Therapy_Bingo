"""HiBid lot profit evaluator: command-line menu.

    python main.py                 # uses items.csv and lots.db in this folder
    python main.py --db mine.db --comps my_items.csv
"""
from __future__ import annotations

import argparse
from dataclasses import fields
from datetime import date, datetime
from pathlib import Path

import store
from evaluator import Comp, append_comp, estimate, load_comps

HERE = Path(__file__).parent


def money(x) -> str:
    if x is None:
        return "—"
    return f"-${-x:,.2f}" if x < 0 else f"${x:,.2f}"


def ask(prompt: str, default=None, cast=str):
    while True:
        suffix = f" [{default}]" if default not in (None, "") else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            return cast(raw.replace("$", "").replace(",", "")) if cast is not str else raw
        except ValueError:
            print("  Please enter a valid value.")


def ask_date(prompt: str) -> str:
    while True:
        raw = ask(prompt, date.today().isoformat())
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date().isoformat()
        except ValueError:
            print("  Use YYYY-MM-DD.")


def table(rows, cols, headers=None, money_cols=()):
    headers = headers or cols
    body = [[money(r[c]) if c in money_cols else str(r[c] if r[c] is not None else "—") for c in cols] for r in rows]
    widths = [max(len(h), *(len(b[i]) for b in body)) if body else len(h) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for b in body:
        print("  ".join(v.rjust(w) if c in money_cols or v.lstrip("-").replace(".", "").isdigit() else v.ljust(w)
                        for v, w, c in zip(b, widths, cols)))


def evaluate(con, comps_path: Path):
    s = store.load_settings(con)
    print("\nDescribe the lot. Separate items with commas, and put quantities first if known.")
    print("  e.g.  10 Stampin Up stamp sets, 2 Creative Memories 12x12 albums, big shot")
    desc = ask("Lot description")
    if not desc:
        return
    s.buyer_premium_pct = ask("Buyer's premium %", s.buyer_premium_pct, float)
    s.lot_shipping = ask("Cost to get the lot (shipping or gas)", s.lot_shipping, float)
    comps = load_comps(comps_path)
    est = estimate(desc, comps, s)

    print()
    for line in est.lines:
        if not line.matches:
            print(f"  ?  {line.qty} x {line.text}: no comps found (not counted). Add some with menu option 6.")
            continue
        print(f"  ✓  {line.qty} x {line.text}: median comp {money(line.unit_value)} each = {money(line.value)}")
        for score, c in line.matches[:3]:
            print(f"        {money(c.sold_price):>8}  {c.brand} {c.item_name} ({c.sold_date}, match {score:.2f})")

    w = 44
    print()
    print(f"  {'Estimated resale (gross)':<{w}}{money(est.gross_resale):>10}")
    print(f"  {f'− eBay fees ({s.ebay_fee_pct:g}% + {money(s.ebay_per_order_fee)}/order)':<{w}}{money(est.ebay_fees):>10}")
    print(f"  {f'− Shipping ({est.items_to_sell} items × {money(s.ship_cost_per_item)})':<{w}}{money(est.shipping):>10}")
    print(f"  {'= Net proceeds':<{w}}{money(est.net_proceeds):>10}")
    print(f"\n  Target: net proceeds ≥ {s.target_multiple:g}× total cost (hammer + {s.buyer_premium_pct:g}% premium"
          f" + {s.sales_tax_pct:g}% tax + {money(s.lot_shipping)} to get the lot)")
    print(f"  >>> MAXIMUM BID: {money(est.max_bid)}  (total cost at that bid: {money(est.total_cost(est.max_bid))})")
    if any(not l.matches for l in est.lines):
        print("  Note: unmatched items aren't counted, so their value is upside on top of this.")

    if ask("\nDid you win this lot? (y/N)", "n").lower().startswith("y"):
        hammer = ask("Winning hammer price", None, float)
        lot_id = store.add_lot(con, ask_date("Purchase date"), ask("Auction name", ""), desc, hammer, s,
                               round(est.gross_resale, 2), round(est.max_bid, 2))
        print(f"  Saved as lot #{lot_id}.")


def record_lot(con):
    s = store.load_settings(con)
    desc = ask("Lot description")
    hammer = ask("Hammer price", None, float)
    s.buyer_premium_pct = ask("Buyer's premium %", s.buyer_premium_pct, float)
    s.lot_shipping = ask("Cost to get the lot", s.lot_shipping, float)
    lot_id = store.add_lot(con, ask_date("Purchase date"), ask("Auction name", ""), desc, hammer, s)
    print(f"  Saved lot #{lot_id}.")


def record_sale(con):
    s = store.load_settings(con)
    lots = store.list_lots(con)
    if not lots:
        print("  No lots yet. Record a purchase first.")
        return
    table(lots[-10:], ["id", "purchase_date", "description", "total_cost"],
          ["#", "date", "description", "cost"], money_cols={"total_cost"})
    lot_ids = {r["id"] for r in lots}
    lot_id = ask("Lot # this item came from", lots[-1]["id"], int)
    if lot_id not in lot_ids:
        print("  Unknown lot #.")
        return
    item = ask("Item")
    price = ask("Sale price (item only)", None, float)
    ship_charged = ask("Shipping charged to buyer", 0.0, float)
    ship_cost = ask("Your actual shipping cost", s.ship_cost_per_item, float)
    fees = ask("eBay fees (Enter to estimate)", store.ebay_fee(price, ship_charged, s), float)
    store.add_sale(con, lot_id, ask_date("Sale date"), item, price, ship_charged, ship_cost, fees)
    print("  Sale saved.")


def report_monthly(con):
    rows = store.monthly_report(con)
    if not rows:
        print("  Nothing recorded yet.")
        return
    print("\nProfit by month (cash basis: lots count when bought, sales when sold)\n")
    cols = ["month", "lots_bought", "lot_spend", "items_sold", "revenue", "fees", "shipping", "profit"]
    table(rows, cols, ["month", "lots", "lot spend", "sold", "revenue", "eBay fees", "shipping", "profit"],
          money_cols={"lot_spend", "revenue", "fees", "shipping", "profit"})
    total = sum(r["profit"] for r in rows)
    print(f"\n  Total profit: {money(total)}")


def report_lots(con):
    rows = store.lot_report(con)
    if not rows:
        print("  No lots yet.")
        return
    print("\nPer-lot results\n")
    table(rows, ["id", "purchase_date", "description", "total_cost", "items_sold", "net_sales", "profit"],
          ["#", "bought", "description", "cost", "sold", "net sales", "profit"],
          money_cols={"total_cost", "net_sales", "profit"})
    for r in rows:
        if r["total_cost"]:
            print(f"  Lot #{r['id']}: {r['net_sales'] / r['total_cost']:.1f}× return so far")


def add_comp(comps_path: Path):
    name = ask("Item name (e.g. Clear mount stamp set)")
    brand = ask("Brand", "Stampin' Up")
    price = ask("Sold price", None, float)
    sold = ask_date("Sold date")
    append_comp(comps_path, Comp(name, brand, price, datetime.strptime(sold, "%Y-%m-%d").date()))
    print(f"  Added to {comps_path.name}.")


def edit_settings(con):
    s = store.load_settings(con)
    print("\nPress Enter to keep a value.")
    for f in fields(s):
        cur = getattr(s, f.name)
        setattr(s, f.name, ask(f"  {f.name}", cur, type(cur)))
    store.save_settings(con, s)
    print("  Saved.")


MENU = """
================ HiBid Lot Evaluator ================
 1) Evaluate a lot (what's my max bid?)
 2) Record a purchased lot
 3) Record a sale
 4) Monthly profit report
 5) Per-lot results
 6) Add a sold comp to items.csv
 7) Settings (fees, premium, shipping, target)
 0) Quit"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=HERE / "lots.db")
    ap.add_argument("--comps", type=Path, default=HERE / "items.csv")
    args = ap.parse_args()
    if not args.comps.exists():
        print(f"{args.comps} not found. Run `python make_sample_data.py` or create it (see README).")
        return
    con = store.connect(args.db)
    actions = {
        "1": lambda: evaluate(con, args.comps), "2": lambda: record_lot(con), "3": lambda: record_sale(con),
        "4": lambda: report_monthly(con), "5": lambda: report_lots(con), "6": lambda: add_comp(args.comps),
        "7": lambda: edit_settings(con),
    }
    while True:
        print(MENU)
        try:
            choice = input("Choose: ").strip()
        except EOFError:
            break
        if choice in ("0", "q", "quit"):
            break
        action = actions.get(choice)
        if action:
            try:
                action()
            except (KeyboardInterrupt, EOFError):
                print("\n  Cancelled.")
        else:
            print("  Pick 0–7.")
    con.close()


if __name__ == "__main__":
    main()
