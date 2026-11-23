# Official exchange classifications

These files hold each exchange's official classification, which Yahoo Finance does not provide:

- `board`: market / board (e.g. Main, ACE, LEAP for Bursa Malaysia; Mainboard, Catalist for SGX)
- `official_sector`: the exchange's sector
- `official_industry`: the exchange's industry or sub-sector

They are maintained by hand. Update them from a source you are licensed to use (for example the exchange's published listing, or your ShareInvestor subscription). Do not scrape exchange websites; Bursa Malaysia and SGX license their market data.

## Format

One file per country: `MY.csv`, `SG.csv`, …

```csv
symbol,board,official_sector,official_industry
0097.KL,Main,Technology,Semiconductors
0249.KL,ACE,Technology,Digital Services
```

- `symbol` must be the Yahoo ticker, including its suffix (`.KL`, `.SI`, …).
- Any column may be left blank. Rows only need to cover the companies you want to correct.

## How the app uses them

- **Board:**
  - A value in this file wins.
  - For Malaysia without a value, the board is inferred from the stock code:
    - `03xxx` → LEAP
    - `1xxx`–`9xxx` → Main
    - `0xxx` → **ACE (unverified)**, because companies that moved from ACE to Main keep their `0xxx` code
    - anything else (ETFs, preference shares, rights) → Other
  - Listing the `0xxx` companies that are on the Main Market is enough to make every Malaysian board correct.
- **Official sector:**
  - When any row has `official_sector`, Sector Search offers an "Official (exchange)" classification.
  - The Excel columns `Category Classification/{exchange}` and `Sector & Industry/ {exchange}` are filled from this file.

Changes take effect after the commit is deployed (about 1–2 minutes on Streamlit Cloud).
