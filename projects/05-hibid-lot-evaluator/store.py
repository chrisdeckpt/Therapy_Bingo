"""SQLite storage for settings, purchased lots, and sales."""
from __future__ import annotations

import sqlite3
from dataclasses import asdict, fields
from pathlib import Path

from evaluator import Settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL NOT NULL);
CREATE TABLE IF NOT EXISTS lots (
    id INTEGER PRIMARY KEY,
    purchase_date TEXT NOT NULL,          -- YYYY-MM-DD
    auction TEXT,
    description TEXT NOT NULL,
    hammer_price REAL NOT NULL,
    buyer_premium REAL NOT NULL,
    tax REAL NOT NULL DEFAULT 0,
    lot_shipping REAL NOT NULL DEFAULT 0,
    est_resale REAL,
    max_bid REAL
);
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    lot_id INTEGER REFERENCES lots(id),
    sale_date TEXT NOT NULL,
    item TEXT NOT NULL,
    sale_price REAL NOT NULL,
    shipping_charged REAL NOT NULL DEFAULT 0,
    shipping_cost REAL NOT NULL DEFAULT 0,
    ebay_fees REAL NOT NULL
);
CREATE VIEW IF NOT EXISTS lot_costs AS
    SELECT *, hammer_price + buyer_premium + tax + lot_shipping AS total_cost FROM lots;
"""


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA)
    return con


def load_settings(con) -> Settings:
    s = Settings()
    for row in con.execute("SELECT key, value FROM settings"):
        if row["key"] in {f.name for f in fields(Settings)}:
            cur = getattr(s, row["key"])
            setattr(s, row["key"], type(cur)(row["value"]))
    return s


def save_settings(con, s: Settings) -> None:
    con.executemany("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)", asdict(s).items())
    con.commit()


def add_lot(con, purchase_date, auction, description, hammer, s: Settings, est_resale=None, max_bid=None) -> int:
    premium = round(hammer * s.buyer_premium_pct / 100, 2)
    tax = round((hammer + premium) * s.sales_tax_pct / 100, 2)
    cur = con.execute(
        "INSERT INTO lots(purchase_date, auction, description, hammer_price, buyer_premium, tax, lot_shipping,"
        " est_resale, max_bid) VALUES (?,?,?,?,?,?,?,?,?)",
        (purchase_date, auction, description, hammer, premium, tax, s.lot_shipping, est_resale, max_bid),
    )
    con.commit()
    return cur.lastrowid


def ebay_fee(sale_price: float, shipping_charged: float, s: Settings) -> float:
    return round((sale_price + shipping_charged) * s.ebay_fee_pct / 100 + s.ebay_per_order_fee, 2)


def add_sale(con, lot_id, sale_date, item, price, ship_charged, ship_cost, fees) -> int:
    cur = con.execute(
        "INSERT INTO sales(lot_id, sale_date, item, sale_price, shipping_charged, shipping_cost, ebay_fees)"
        " VALUES (?,?,?,?,?,?,?)",
        (lot_id, sale_date, item, price, ship_charged, ship_cost, fees),
    )
    con.commit()
    return cur.lastrowid


def monthly_report(con) -> list[sqlite3.Row]:
    """Cash-basis profit by month: lot spending counts in the month bought, sales in the month sold."""
    return con.execute(
        """
        WITH months AS (
            SELECT substr(purchase_date, 1, 7) AS month FROM lots
            UNION SELECT substr(sale_date, 1, 7) FROM sales
        ),
        buys AS (SELECT substr(purchase_date, 1, 7) AS month, COUNT(*) AS lots_bought,
                        SUM(total_cost) AS lot_spend FROM lot_costs GROUP BY 1),
        sells AS (SELECT substr(sale_date, 1, 7) AS month, COUNT(*) AS items_sold,
                         SUM(sale_price + shipping_charged) AS revenue, SUM(ebay_fees) AS fees,
                         SUM(shipping_cost) AS shipping
                  FROM sales GROUP BY 1)
        SELECT m.month,
               COALESCE(b.lots_bought, 0) AS lots_bought, COALESCE(b.lot_spend, 0) AS lot_spend,
               COALESCE(s.items_sold, 0) AS items_sold, COALESCE(s.revenue, 0) AS revenue,
               COALESCE(s.fees, 0) AS fees, COALESCE(s.shipping, 0) AS shipping,
               COALESCE(s.revenue, 0) - COALESCE(s.fees, 0) - COALESCE(s.shipping, 0)
                   - COALESCE(b.lot_spend, 0) AS profit
        FROM months m LEFT JOIN buys b USING (month) LEFT JOIN sells s USING (month)
        ORDER BY m.month
        """
    ).fetchall()


def lot_report(con) -> list[sqlite3.Row]:
    return con.execute(
        """
        SELECT l.id, l.purchase_date, l.description, l.total_cost, l.est_resale,
               COUNT(s.id) AS items_sold,
               COALESCE(SUM(s.sale_price + s.shipping_charged - s.ebay_fees - s.shipping_cost), 0) AS net_sales,
               COALESCE(SUM(s.sale_price + s.shipping_charged - s.ebay_fees - s.shipping_cost), 0) - l.total_cost AS profit
        FROM lot_costs l LEFT JOIN sales s ON s.lot_id = l.id
        GROUP BY l.id ORDER BY l.purchase_date
        """
    ).fetchall()


def list_lots(con) -> list[sqlite3.Row]:
    return con.execute("SELECT id, purchase_date, description, total_cost FROM lot_costs ORDER BY id").fetchall()
