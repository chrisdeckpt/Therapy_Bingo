"""Create sample comps (items.csv) and a demo SQLite database (lots.db) with a few lots and sales.

Prices are made up for demonstration. Replace items.csv with your own sold comps.
Sold dates are set relative to today so the samples stay inside the comp window.
"""
import random
from datetime import date, timedelta
from pathlib import Path

import store
from evaluator import Comp, Settings, append_comp

HERE = Path(__file__).parent

# (item name, brand, typical sold price)
CATALOG = [
    ("Clear mount stamp set", "Stampin' Up", 14),
    ("Wood mount stamp set", "Stampin' Up", 18),
    ("Photopolymer stamp set", "Stampin' Up", 16),
    ("Stamp set and matching dies bundle", "Stampin' Up", 32),
    ("Framelits dies", "Stampin' Up", 15),
    ("Thinlits dies", "Stampin' Up", 14),
    ("Embossing folder", "Stampin' Up", 8),
    ("Classic ink pad", "Stampin' Up", 6),
    ("Stampin' Blends alcohol markers", "Stampin' Up", 12),
    ("Designer series paper pack", "Stampin' Up", 9),
    ("Big Shot die cutting machine", "Stampin' Up", 55),
    ("Stampin' Trimmer paper cutter", "Stampin' Up", 20),
    ("Punch", "Stampin' Up", 10),
    ("Ribbon spool", "Stampin' Up", 5),
    ("12x12 strap-hinge album", "Creative Memories", 22),
    ("8x8 coverset album", "Creative Memories", 14),
    ("Refill page protectors 12x12", "Creative Memories", 12),
    ("Custom cutting system", "Creative Memories", 25),
    ("Personal trimmer", "Creative Memories", 15),
    ("Border maker cartridge", "Creative Memories", 11),
    ("Circle cutter", "Creative Memories", 18),
    ("Corner rounder punch", "Creative Memories", 9),
    ("Sticker sheets", "Creative Memories", 4),
    ("Cardstock pack 12x12", "Creative Memories", 8),
]


def make_items(rng: random.Random, today: date) -> None:
    path = HERE / "items.csv"
    path.unlink(missing_ok=True)
    for name, brand, base in CATALOG:
        for _ in range(rng.randint(3, 6)):
            price = max(1.0, rng.gauss(base, base * 0.25))
            when = today - timedelta(days=rng.randint(3, 300))
            append_comp(path, Comp(name, brand, round(price, 2), when))
    print(f"Wrote {path.name}")


def make_db(rng: random.Random, today: date) -> None:
    db = HERE / "lots.db"
    db.unlink(missing_ok=True)
    con = store.connect(db)
    s = Settings()
    store.save_settings(con, s)
    lots = [
        (150, "Estate auction", "12 Stampin Up stamp sets, 4 framelits, big shot", 85.0),
        (95, "Church craft sale online", "3 Creative Memories 12x12 albums, custom cutting system", 22.5),
        (40, "Weekly HiBid", "8 Stampin Up ink pads, 10 designer series paper, 5 punches", 30.0),
    ]
    for days_ago, auction, desc, hammer in lots:
        lot_id = store.add_lot(con, (today - timedelta(days=days_ago)).isoformat(), auction, desc, hammer, s)
        for _ in range(rng.randint(4, 9)):
            sold = today - timedelta(days=rng.randint(0, max(1, days_ago - 5)))
            price = round(rng.uniform(6, 40), 2)
            ship = 5.99
            store.add_sale(con, lot_id, sold.isoformat(), f"Item from lot {lot_id}", price, ship,
                           round(rng.uniform(4.5, 8), 2), store.ebay_fee(price, ship, s))
    print(f"Wrote {db.name} with {len(lots)} demo lots")


if __name__ == "__main__":
    import sys

    existing = [p.name for p in (HERE / "items.csv", HERE / "lots.db") if p.exists()]
    if existing and "--force" not in sys.argv:
        sys.exit(f"{', '.join(existing)} already exist. These may hold your real comps or sales.\n"
                 "Re-run with --force to replace them with sample data.")
    rng = random.Random(3)
    today = date.today()
    make_items(rng, today)
    make_db(rng, today)
