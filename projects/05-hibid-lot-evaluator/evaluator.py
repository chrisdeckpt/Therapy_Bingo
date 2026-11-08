"""Match a lot description to sold eBay comps and work out a maximum bid."""
from __future__ import annotations

import csv
import re
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

STOPWORDS = {"a", "an", "and", "the", "of", "with", "lot", "lots", "set", "sets", "assorted", "misc",
             "various", "new", "used", "nib", "in", "box", "for", "pc", "pcs", "piece", "pieces", "x"}
BRAND_ALIASES = {
    "stampin up": "stampin up", "stampinup": "stampin up", "su": "stampin up",
    "creative memories": "creative memories", "cm": "creative memories",
}
WORD_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10, "dozen": 12}


@dataclass
class Comp:
    item_name: str
    brand: str
    sold_price: float
    sold_date: date

    @property
    def tokens(self) -> set[str]:
        return tokens(f"{self.brand} {self.item_name}")


@dataclass
class Settings:
    ebay_fee_pct: float = 13.25        # final value fee, % of (sale price + shipping charged)
    ebay_per_order_fee: float = 0.40   # fixed per-order fee
    ship_cost_per_item: float = 6.50   # what you pay to ship each item you sell
    buyer_premium_pct: float = 15.0    # auction house buyer's premium
    sales_tax_pct: float = 0.0         # tax on hammer + premium, if you pay it
    lot_shipping: float = 0.0          # cost to get the lot to you (shipping or gas)
    target_multiple: float = 3.0       # net proceeds / total cost
    comp_window_days: int = 365        # ignore comps older than this
    min_match_score: float = 0.34


@dataclass
class LineEstimate:
    text: str
    qty: int
    matches: list[tuple[float, Comp]] = field(default_factory=list)

    @property
    def unit_value(self) -> float | None:
        if not self.matches:
            return None
        return statistics.median(c.sold_price for _, c in self.matches)

    @property
    def value(self) -> float:
        return (self.unit_value or 0.0) * self.qty


@dataclass
class LotEstimate:
    lines: list[LineEstimate]
    settings: Settings

    @property
    def matched_lines(self):
        return [l for l in self.lines if l.matches]

    @property
    def items_to_sell(self) -> int:
        return sum(l.qty for l in self.matched_lines)

    @property
    def gross_resale(self) -> float:
        return sum(l.value for l in self.lines)

    @property
    def ebay_fees(self) -> float:
        s = self.settings
        return self.gross_resale * s.ebay_fee_pct / 100 + s.ebay_per_order_fee * self.items_to_sell

    @property
    def shipping(self) -> float:
        return self.settings.ship_cost_per_item * self.items_to_sell

    @property
    def net_proceeds(self) -> float:
        return self.gross_resale - self.ebay_fees - self.shipping

    def total_cost(self, hammer: float) -> float:
        s = self.settings
        return hammer * (1 + s.buyer_premium_pct / 100) * (1 + s.sales_tax_pct / 100) + s.lot_shipping

    @property
    def max_bid(self) -> float:
        """Largest hammer price where net proceeds >= target_multiple x total cost."""
        s = self.settings
        budget = self.net_proceeds / s.target_multiple - s.lot_shipping
        hammer = budget / ((1 + s.buyer_premium_pct / 100) * (1 + s.sales_tax_pct / 100))
        return max(0.0, hammer)


def normalize(text: str) -> str:
    t = text.lower().replace("’", "'").replace("'", "").replace("-", " ")
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = " " + re.sub(r"\s+", " ", t).strip() + " "
    for alias, canonical in sorted(BRAND_ALIASES.items(), key=lambda kv: -len(kv[0])):
        t = t.replace(f" {alias} ", f" {canonical} ")
    return t.strip()


def stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and re.search(r"(ch|sh|x|ss)es$", word):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokens(text: str) -> set[str]:
    return {stem(w) for w in normalize(text).split() if w not in STOPWORDS and not w.isdigit()}


def split_lot(description: str) -> list[tuple[int, str]]:
    """'3 Stampin Up stamp sets, 2 CM albums & punches' -> [(3, 'Stampin Up stamp sets'), (2, 'CM albums'), (1, 'punches')]."""
    parts = re.split(r"[,;\n+&]|\band\b|\s/\s", description, flags=re.I)
    out = []
    for p in parts:
        p = p.strip(" .-")
        if not p:
            continue
        m = re.match(r"^\(?(\d+)\)?\s*x?\s+(.*)$", p, flags=re.I) or re.match(r"^(\w+)\s+(.*)$", p)
        qty = 1
        if m:
            first = m.group(1).lower()
            if first.isdigit():
                qty, p = int(first), m.group(2)
            elif first in WORD_NUMBERS:
                qty, p = WORD_NUMBERS[first], m.group(2)
        out.append((max(qty, 1), p.strip()))
    return out


def similarity(query: set[str], comp: Comp, brand_words: set[str]) -> float:
    """Score 0..~1. Item words must overlap. Brand words add a bonus, or rule a comp out if another brand is named."""
    q_core = query - brand_words
    c_brand = tokens(comp.brand)
    c_core = comp.tokens - brand_words
    overlap = q_core & c_core
    if not overlap:
        return 0.0
    # Mostly: how much of what was asked for does this comp cover? Then: how specific is the comp?
    score = 0.6 * len(overlap) / len(q_core) + 0.4 * len(overlap) / len(c_core)
    if query & brand_words and c_brand:
        if not c_brand <= query:
            return 0.0  # the lot names a different brand, so this comp doesn't apply
        score += 0.1
    return score


def load_comps(path: Path) -> list[Comp]:
    comps = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            comps.append(Comp(row["item_name"].strip(), row["brand"].strip(), float(row["sold_price"]),
                              datetime.strptime(row["sold_date"].strip(), "%Y-%m-%d").date()))
    return comps


def append_comp(path: Path, comp: Comp) -> None:
    new_file = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["item_name", "brand", "sold_price", "sold_date"])
        w.writerow([comp.item_name, comp.brand, f"{comp.sold_price:.2f}", comp.sold_date.isoformat()])


def estimate(description: str, comps: list[Comp], settings: Settings, today: date | None = None,
             top_n: int = 12) -> LotEstimate:
    today = today or date.today()
    cutoff = today - timedelta(days=settings.comp_window_days)
    recent = [c for c in comps if c.sold_date >= cutoff]
    brand_words = set().union(*(tokens(c.brand) for c in comps)) if comps else set()
    lines = []
    for qty, text in split_lot(description):
        q = tokens(text)
        scored = sorted(((similarity(q, c, brand_words), c) for c in recent), key=lambda x: -x[0])
        if not scored or scored[0][0] < settings.min_match_score:
            lines.append(LineEstimate(text, qty, []))
            continue
        best = scored[0][0]
        # keep comps close to the best score so one item's comps aren't diluted by loose matches
        keep = [(s, c) for s, c in scored if s >= max(settings.min_match_score, best - 0.15)][:top_n]
        lines.append(LineEstimate(text, qty, keep))
    return LotEstimate(lines, settings)
