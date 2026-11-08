# HiBid lot evaluator

A small command-line tool for deciding **how much to bid** on auction lots that you plan to resell
on eBay (papercraft: Stampin' Up, Creative Memories), and for **tracking what you bought and sold**.

Uses only the Python standard library (3.9+). Nothing to install except `pytest` for the tests.

## Quick start

```bash
cd 05-hibid-lot-evaluator
python make_sample_data.py   # sample items.csv + demo lots.db (refuses to overwrite without --force)
python main.py
```

```
 1) Evaluate a lot (what's my max bid?)
 2) Record a purchased lot
 3) Record a sale
 4) Monthly profit report
 5) Per-lot results
 6) Add a sold comp to items.csv
 7) Settings (fees, premium, shipping, target)
```

## How the max bid is calculated

1. **Split the lot description** at commas, `&`, "and", `;`, and line breaks. A leading number
   (`10 stamp sets`) or number word (`two albums`) sets the quantity. Otherwise the quantity is 1.
2. **Match each piece to comps** in `items.csv`, using comps sold in the last 365 days. The item
   words have to overlap. Brand words alone ("Stampin Up …") never count as a match. If you name a
   brand, comps from other brands are ignored. Abbreviations `SU` and `CM` work.
3. **Value each matched item at the median sold price** of its closest comps, times quantity.
   Items with no match are listed but **not counted**, so they're extra upside.
4. **Net proceeds** = resale − eBay fees (13.25% plus $0.40 per order) − your shipping cost per item.
5. **Max bid**: the hammer price where net proceeds = **3 × total cost**, and total cost = hammer
   + buyer's premium + sales tax (if any) + cost to get the lot home.

   `max bid = (net proceeds ÷ 3 − lot shipping) ÷ ((1 + premium%) × (1 + tax%))`

So "3× return" here means every $1 you spend on the lot should bring back $3 after fees and
shipping. Change the multiple, fees, premium, shipping, and comp window under menu option 7.
They're saved in the database.

Example (sample data):

```
  ✓  10 x Stampin Up stamp sets: median comp $16.73 each = $167.35
  ✓  1 x big shot: median comp $48.84 each = $48.84
  Estimated resale (gross)                       $216.19
  − eBay fees (13.25% + $0.40/order)              $33.05
  − Shipping (11 items × $6.50)                   $71.50
  = Net proceeds                                 $111.64
  >>> MAXIMUM BID: $32.36  (total cost at that bid: $37.21)
```

## items.csv: your sold comps

```csv
item_name,brand,sold_price,sold_date
Clear mount stamp set,Stampin' Up,14.50,2026-10-02
12x12 strap-hinge album,Creative Memories,22.00,2026-09-18
```

- Copy prices from eBay **Sold** listings, not active listings. Use the item price only, without shipping.
- Name items the way lots describe them ("stamp set", "album", "punch", "big shot"). Matching is
  word-based, so shared words matter more than exact titles.
- Add comps from the menu (option 6) or edit the CSV in Excel or Google Sheets.
- **The sample prices are made up.** Replace them with your own comps before you bid real money.

## Tracking (lots.db, SQLite)

- **Record a purchased lot**: hammer price, premium, and tax are saved. Option 1 also offers to
  save a lot you just evaluated and won, with its estimate.
- **Record a sale**: link it to the lot it came from. eBay fees are estimated, but you can type the
  actual amount from your eBay order.
- **Monthly profit report**: cash basis. Lot spending counts in the month you bought the lot, and
  sales count in the month they sold, so a big buying month can show a loss.
- **Per-lot results**: net sales, profit, and return multiple for each lot so far.

`lots.db` is in `.gitignore`. Back it up yourself, for example by copying it to cloud storage.
Open it in any SQLite viewer (such as DB Browser for SQLite) to run your own queries.

## Tests

```bash
pip install pytest
python -m pytest -q
```
