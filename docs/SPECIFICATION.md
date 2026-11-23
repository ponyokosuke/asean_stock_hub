# ASEAN Stock Analysis Hub — System Specification

| Item | Value |
|---|---|
| Document version | 1.0 |
| Date | 2026-11-23 |
| Applies to | `main` branch of `ponyokosuke/asean_stock_hub` (after PR #1) |
| Live app | https://aseanstockapp-analysis.streamlit.app/ |
| Status | Describes the system **as built**. Section 14 lists known gaps and the target behaviour for each. |

---

## 1. Purpose and scope

The ASEAN Stock Analysis Hub is an internal web tool. It helps the team identify listed companies in ASEAN markets, especially IT-related companies, and produce a standardised financial research sheet (Excel) for each list of companies.

In scope:

- Building company lists by sector, by uploaded CSV, or by AI judgement of business descriptions.
- Retrieving public financial and profile data for each company from Yahoo Finance.
- Producing a formatted Excel workbook with a fixed column layout used by the research team.
- Comparing two lists to see which companies were added or dropped.

Out of scope:

- Real-time prices, trading, or investment advice.
- Unlisted companies.
- Official exchange classifications (see Section 5.3 and Section 14).

## 2. Users and access

| Role | Description |
|---|---|
| Researcher | Runs searches and downloads Excel files (e.g. Elaine). |
| Maintainer | Edits default lists, prompts and code on GitHub (e.g. Kosuke). |

- Access is protected by one shared password (`APP_PASSWORD`).
- After a correct login the session stays authenticated until the browser tab is closed or the app restarts.
- **If `APP_PASSWORD` is not configured, the app is open to anyone** (see Section 14, issue SEC-1).

## 3. Glossary

| Term | Meaning |
|---|---|
| Code / Ticker | Yahoo Finance symbol, e.g. `0097.KL`, `D05.SI`. |
| Suffix | Market part of the ticker: `.SI` SGX, `.KL` Bursa Malaysia, `.BK` SET, `.JK` IDX, `.PS` PSE, `.VN` HOSE. |
| Sector master | `data/sector_master.csv`, the list of all listed companies with their Yahoo sector. |
| Default list | `templates/{COUNTRY}.csv`, a curated code list per country used by Version 1. |
| Board / Market (Malaysia) | Bursa Malaysia segment: Main Market, ACE Market or LEAP Market. |
| `('000)` | Values divided by 1,000, in the company's reporting currency. |

## 4. System overview

```
 Researcher ──HTTPS──▶ Streamlit Community Cloud (app)
                           │   reads  data/sector_master.csv, templates/*.csv
                           │   calls  Yahoo Finance (yfinance) per company
                           │   calls  Google Gemini (gemini-2.5-flash)
                           ▼
                     Excel download (.xlsx)

 GitHub repository ──push──▶ Streamlit Cloud redeploys automatically
 GitHub Actions (daily 22:00 UTC / 06:00 SGT)
     └─ scripts/build_sector_master.py ──▶ Yahoo screener ──▶ commits data/ if changed
```

| Component | Technology |
|---|---|
| UI / server | Streamlit (multi-page app). Entry point is `Home.py`; the screens are in `pages/`. |
| Data access | `yfinance` ≥ 1.0 (unofficial Yahoo Finance API). |
| AI | Google Gemini via the `google-genai` SDK, model `gemini-2.5-flash`. |
| Excel | `pandas` + `openpyxl`. |
| Scheduler | GitHub Actions workflow `update_sector_master.yml`. |
| Hosting | Streamlit Community Cloud, deployed from `main`. |

### 4.1 Code structure

| Path | Responsibility |
|---|---|
| `Home.py` | Landing page and login. |
| `pages/01_Financial_Data.py` | Version 1: Financial Data. |
| `pages/02_Sector_Search.py` | Version 2: Sector Search. |
| `pages/03_AI_Judge.py` | Version 3: AI Judge. |
| `pages/04_Compare_Lists.py` | Compare Lists. |
| `pages/05_Specification.py` | Shows this document inside the app. |
| `utils/auth.py` | Password check. |
| `utils/ui.py` | Country selector in the sidebar. |
| `utils/codes.py` | Parses code lists from CSV. |
| `utils/analysis.py` | Shared pipeline: fetch → AI segments → Excel. |
| `utils/sector_master.py` | Loads the sector master; country and sector constants. |
| `utils/processors/` | Country-specific settings (currency, suffix, column names). |
| `scripts/build_sector_master.py` | Builds the sector master. |
| `templates/` | Default code lists per country. |
| `data/` | Sector master and its metadata. |

## 5. Supported markets

| Country | Code | Suffix | Currency label | Sector master | Default list |
|---|---|---|---|---|---|
| Singapore | SG | `.SI` | SGD | Yes (535) | Yes (70 codes, curated IT list) |
| Malaysia | MY | `.KL` | MYR | Yes (1,087) | Yes (129 codes, Yahoo "Technology") |
| Thailand | TH | `.BK` | THB | Yes (1,517) | No |
| Indonesia | ID | `.JK` | IDR | Yes (838) | No |
| Philippines | PH | `.PS` | PHP | **No** (not covered by the Yahoo screener) | No |
| Vietnam | VN | `.VN` | VND | **No** (not covered by the Yahoo screener) | No |

Counts are as of 2026-11-23 and change with each master update.

### 5.1 Singapore

- The master contains all SGX securities that Yahoo classifies as equities (exchange `SES`).
- This includes some foreign depositary receipts, such as `HPCD.SI`.

### 5.2 Thailand

- NVDR (`-R.BK`) and foreign-board (`-F.BK`) lines are excluded, because they duplicate the underlying company.

### 5.3 Malaysia — market boards (Main / ACE / LEAP)

Bursa Malaysia has three boards:

| Board | Description | Typical stock code |
|---|---|---|
| Main Market | Large, established companies | 4 digits starting 1–9 (e.g. `1155`), **or** a `0xxx` code kept after a transfer from ACE |
| ACE Market | Growth companies (sponsor-driven) | 4 digits starting with `0` (e.g. `0249`) |
| LEAP Market | Qualified/sophisticated investors only | 5 digits starting with `03` (e.g. `03011`) |

**Current behaviour:**

- The sector master does **not** record the board. Every Malaysian row has exchange `KLS`.
  - As of 2026-11-23: 704 codes are `[1-9]xxx`, 360 are `0xxx`, 3 are `03xxx`, and 20 carry an instrument suffix.
- `BaseProcessor.extract_data` derives a `Market` value from the code: `03xxx` → LEAP, `0xxx` → ACE, `[1-9]xxx` → Main, anything else → Main/Other.
  - This rule is **wrong for companies that moved from ACE to Main Market**, because they keep their original `0xxx` code.
  - The `Market` value is **not written to the Excel output**, because it is missing from the column order (issue DATA-2).
- The Malaysian master also includes non-ordinary-share instruments (issue DATA-3):
  - ETFs (`…EA`, 11)
  - Preference shares (`…PA`/`…PC`, 7)
  - Stapled securities (`…SS`, 1)
  - Rights (`…R1`, 1)
- Bursa Malaysia's own data endpoints are protected by bot checks and cannot be fetched automatically.

**Target behaviour:** see issue DATA-1 in Section 14.

## 6. Data sources

| Data | Source | Notes |
|---|---|---|
| Company list and sector | Yahoo Finance equity screener (`yf.screen`) | One query per country × sector, 250 rows per page. Sector taxonomy is Yahoo/Morningstar, **not** the exchange's official sector. |
| Profile, financial statements, holders | `yf.Ticker(code)`: `.info`, `.financials`, `.balance_sheet`, `.major_holders`, `.institutional_holders` | Annual statements; latest fiscal year column. |
| FX rate | `yf.Ticker("{CUR}SGD=X")` | Previous close; falls back to the last close of the past 5 days. |
| Business segments | Gemini, using the Yahoo business summary | AI-generated; not audited figures. |
| IT judgement (V3) | Gemini, using the Yahoo business summary and the editable prompt | AI-generated. |

## 7. Functional specification

### 7.1 Common behaviour (all pages)

1. **Login:** every page calls `check_password()` before rendering anything.
2. **Country selector:** a radio button in the sidebar (SG, MY, VN, ID, TH, PH).
   - Default is SG.
   - The choice is kept in `st.session_state["target_country"]` across pages.
3. **Processor:** the selected country decides the ticker suffix, the currency label and any country-specific column names.
4. **Debug Mode:** a sidebar checkbox that shows full Python tracebacks when an error occurs.

### 7.2 Code list parsing (`utils/codes.py`)

Used by Version 1, both for uploads and for default lists.

| Rule | Behaviour |
|---|---|
| Column | Reads the first column only, as text (leading zeros are kept). |
| Normalisation | Trims spaces and converts to upper case. |
| Header | Skips values that do not look like a code, and the words CODE, CODES, SYMBOL, TICKER, STOCK. |
| Suffix | Adds the country suffix when a code has none (`0097` → `0097.KL`). |
| Duplicates | Removed; the first occurrence order is kept. |
| Empty file | Returns an empty list (no error). |

### 7.3 Version 1 — Financial Data

**Purpose:** produce the research Excel for a given list of codes.

| Element | Specification |
|---|---|
| Upload | One CSV file with one code per row. |
| Default list | Checkbox "Use default list for {country} (N codes)". Disabled and marked "Not registered" when the list is missing or empty. |
| Sidebar | Read-only view of the default list, with a link to edit `templates/{country}.csv` on GitHub. |
| Precedence | An uploaded file takes priority over the default list. |
| Run | "Start Analysis" runs the shared pipeline (Section 8) with the file prefix `Version_1`. |
| Errors | No input → "Please upload a CSV file or select the default list." No valid codes → explains the expected format. |

Default lists cannot be edited inside the app. Streamlit Cloud deletes files written at runtime whenever the app restarts.

### 7.4 Version 2 — Sector Search

**Purpose:** find companies by sector and produce the same Excel as Version 1.

1. Loads the sector master for the selected country.
   - If the country has no rows (PH, VN), shows a message pointing to Version 1 and stops.
2. Shows the number of companies and the date the master was last updated.
3. **Select Target Sectors:** multi-select of the 11 Yahoo sectors plus "Unknown", each showing its company count.
4. **Filter by company name:** optional, case-insensitive substring match.
5. A table of matching companies (Code, Name of Company, Sector) with a **Select** checkbox per row. All rows are ticked by default.
6. **Download code list:** a CSV of the ticked codes, one per line.
7. **Start Financial Analysis (N companies):** runs the shared pipeline with the file prefix `Version_2`.
   - Selections larger than 100 companies show a warning about run time.

No Yahoo requests are made until the analysis starts.

### 7.5 Version 3 — AI Judge

**Purpose:** use AI to decide which companies are IT-related, then produce the Excel for those judged "Yes".

1. **Prompt editor:** the system prompt can be edited for the session.
   - "Save Current Prompt as Default" writes `prompts/it_judge_prompt.txt`. This file is lost when the app restarts (issue OPS-2).
   - "Reset to System Original" restores the built-in prompt.
2. **Target Sectors:** candidates come from the sector master, filtered by sector.
   - Default: Technology and Communication Services.
3. **Step 1:** fetch `longBusinessSummary` for each candidate (0.3 s pause between requests).
   - Companies without a summary are skipped.
4. **Step 2:** send the summaries to Gemini in batches of 30, each summary truncated to 800 characters.
   - Expected JSON response: `{code: {verdict: Yes|No|Grey, category, reason}}`.
5. **Step 3:** companies with verdict "Yes" go through the shared pipeline with the file prefix `Version_3_AI_Judge`.
   - Their "Category Classification/YahooFin" value is replaced by `"{category} (AI Judged)"`.

Built-in criteria:

- **Yes:**
  - Software and IT services
  - IT hardware and semiconductors
  - Telecommunications
- **No:**
  - Companies that only use IT, including fintech, e-commerce retail and general manufacturing
- **Grey:**
  - Mixed businesses, or summaries too vague to judge

### 7.6 Compare Lists

**Purpose:** compare two lists (for example a V1 output and a V3 output).

1. Upload File A (base) and File B (target), each in CSV, XLS or XLSX format.
2. Finding the code column:
   - Uses the first column whose name is Code, Stock Code, Symbol or Ticker (case-insensitive).
   - Otherwise uses the first column.
3. Shows counts for: Common, Only in A (dropped), and Only in B (added).
4. For a selected group, "Fetch Details" retrieves Name, Sector, Industry and Business Summary from Yahoo (0.5 s pause), shows a table and offers an Excel download.

### 7.7 Specification

Shows this document (`docs/SPECIFICATION.md`) inside the app, behind the same login, with a Markdown download button.

## 8. Shared analysis pipeline (`utils/analysis.py`)

For each code, in order:

1. **Fetch:** `processor.get_stock_data(code)`.
   - `.info` is retried up to 3 times, waiting 2, 4 and 8 seconds.
   - If all attempts fail, the code is recorded as failed.
   - The statements and holders are then requested.
2. **Extract:** `processor.extract_data(code, raw)` builds one row (Section 9).
3. Pause 0.3 s between companies.

After the loop:

4. Any failed codes are listed in a warning.
5. If no rows were retrieved, an error message suggests waiting and retrying.
6. **AI segments:** `run_ai_analysis` sends business summaries to Gemini in batches of 20 (500 characters each) and fills `Segments`.
   - Skipped silently if `GEMINI_API_KEY` is not set.
7. **Formatting:** `process_dataframe` converts monetary columns to thousands and renames them with `('000)`.
   - SG renames REVENUE to `REVENUE SGD('000)`, MY to `REVENUE MYR('000)` and VN to `REVENUE VND('000)`.
8. **Excel:** `generate_excel_binary` (Section 9).
9. Shows a download button, named `{prefix}_{COUNTRY}_{YYYY-MM-DD}.xlsx`, and a preview table.

## 9. Excel output specification

One worksheet. Header row filled in yellow (`#FEFE99`) and bold. Columns appear in this exact order:

| # | Column | Source / rule | Format |
|---|---|---|---|
| 1 | Ref | Row number, starting at 1 | |
| 2 | Name of Company | `info.longName` | |
| 3 | Code | Yahoo ticker | |
| 4 | Listed 'o' / Non Listed "x" | Always `o` | |
| 5 | Taka's comments | Blank (manual) | |
| 6 | Remarks | Blank (manual) | |
| 7 | Visited (V) / Meeting Proposal (MP) | Blank (manual) | |
| 8 | Website | `info.website` | |
| 9 | Major Shareholders | Top 5 lines of `major_holders`; if empty, top 10 of `institutional_holders`; else "Not Available" | |
| 10 | Currency | `info.financialCurrency`, else `info.currency`; CNY shown as "RMB (CNY)" | |
| 11 | Exchange Rate (to SGD) ({Mon DD}, Closing) | `{CUR}SGD=X` previous close; 1.0 for SGD | `0.0000` |
| 12 | FY | `info.lastFiscalYearEnd` (date) | right-aligned |
| 13 | REVENUE {CUR}('000) | Income statement "Total Revenue" | `#,##0;(#,##0)` |
| 14 | Segments | Gemini, from business summary | |
| 15 | PROFIT ('000) | "Pretax Income"; if 0, "Operating Income" | `#,##0;(#,##0)` |
| 16 | GROSS PROFIT ('000) | "Gross Profit" | same |
| 17 | OPERATING PROFIT ('000) | "Operating Income" | same |
| 18 | NET PROFIT (Group) ('000) | "Net Income Including Noncontrolling Interests"; else "Net Income Continuous Operations"; else Net Profit (Shareholders) | same |
| 19 | NET PROFIT (Shareholders) ('000) | "Net Income"; else "Net Income Common Stock" | same |
| 20 | Minority Interest ('000) | Balance sheet "Minority Interest" | same |
| 21 | Shareholders' Equity ('000) | "Stockholders Equity" | same |
| 22 | Total Equity ('000) | "Total Equity Gross Minority Interest"; else Shareholders' Equity + Minority Interest | same |
| 23 | TOTAL ASSET ('000) | "Total Assets" | same |
| 24 | Debt/Equity(%) | (Total Assets − Total Equity) ÷ Total Equity, i.e. **total liabilities** to equity | `0.00%` |
| 25 | Loan ('000) | "Total Debt"; else "Current Debt" + "Long Term Debt" | `#,##0;(#,##0)` |
| 26 | Loan/Equity (%) | Loan ÷ Total Equity | `0.00%` |
| 27 | Stock Price ({Mon DD}, Closing) | `info.previousClose`, else `regularMarketPrice` | `#,##0.000` |
| 28 | Shares Outstanding ('000) | `info.sharesOutstanding` | `#,##0;(#,##0)` |
| 29 | Market Cap ('000) | Stock Price × Shares Outstanding; else `info.marketCap` | same |
| 30 | Summary of Business | `info.longBusinessSummary` | |
| 31 | Chairman / CEO | First officer whose title contains "CEO" or "Chairman"; else the first officer | |
| 32 | Address | address1, address2, city, country, zip | |
| 33 | Contact No. | `info.phone` | |
| 34 | Access | Blank (manual) | |
| 35 | Last Communications | Blank (manual) | |
| 36 | Number of Employee Current | `info.fullTimeEmployees` | |
| 37 | Category Classification/YahooFin | `info.sector` (V3: AI category + " (AI Judged)") | |
| 38 | Sector & Industry/YahooFin | `info.industry` | |
| 39 | Category Classification/ShareInvestor | Blank (manual) | |
| 40 | Incorporated (IN / Year) | Blank (manual) | |
| 41 | Category Classification/SGX | Blank (manual) | |
| 42 | Sector & Industry/ SGX | Blank (manual) | |

Rules:

- All financial figures come from the **latest annual** statement column.
- `{Mon DD}` is the server's date minus one day.
- Missing statement items are written as **0**, not blank (issue DATA-5).

## 10. Sector master specification

### 10.1 Schema — `data/sector_master.csv`

| Column | Type | Example | Description |
|---|---|---|---|
| country | text | `MY` | App country code |
| symbol | text | `0097.KL` | Yahoo ticker |
| name | text | `ViTrox Corporation Berhad` | `longName`, else `shortName` |
| sector | text | `Technology` | One of the 11 Yahoo sectors, or `Unknown` |
| exchange | text | `KLS` | Yahoo exchange code |

The file is sorted by country, sector and symbol.

### 10.2 Metadata — `data/sector_master_meta.json`

`{"updated_at": "YYYY-MM-DD HH:MM UTC", "counts": {country: rows}}`. It is written only when the CSV content changes.

### 10.3 Build process (`scripts/build_sector_master.py`)

1. For each country in `COUNTRY_REGIONS` (SG, MY, TH, ID) and each of the 11 sectors, query the screener with `region = r AND sector = s`.
   - Results are paged 250 at a time, sorted by market cap.
   - Pages are 1 s apart; failed pages retry up to 4 times with 5, 10, 20 and 40 s waits.
2. Query the whole region again and add symbols that are not in any sector, as `Unknown`.
3. **Safeguard:** if a country returns fewer than 50 % of its previous row count, keep the previous rows for that country.
4. Remove Thai `-R.BK` and `-F.BK` lines.
5. If the resulting CSV text is identical to the existing file, stop with "No changes".
6. Otherwise write the CSV and the metadata.

### 10.4 Schedule

- GitHub Actions runs `update_sector_master.yml` daily at 22:00 UTC, and can also be started manually ("Run workflow").
- It commits `data/` only when something changed. Each such commit triggers a Streamlit redeploy.

## 11. Configuration

| Setting | Where | Required | Purpose |
|---|---|---|---|
| `APP_PASSWORD` | Streamlit Secrets or environment variable | Strongly recommended | Login password. If unset, there is no login. |
| `GEMINI_API_KEY` | Streamlit Secrets or environment variable | For AI features | Segments (all versions) and AI Judge (V3). |
| `templates/{COUNTRY}.csv` | Repository | Optional | Default list for V1. |

Secrets must never be committed. `.streamlit/secrets.toml` in the repository is empty and must stay empty.

## 12. Non-functional requirements and characteristics

| Topic | Current characteristic |
|---|---|
| Performance | About 3–6 s per company in the pipeline. 129 companies take roughly 8–13 minutes, plus AI time. |
| Rate limits | Yahoo may throttle shared cloud IPs. Mitigation: pauses, retries with backoff, and a failed-code report. |
| Session | Results live only in the browser session. Closing the tab, or any rerun after completion, clears them (issue UX-1). |
| Availability | Streamlit Community Cloud sleeps the app after inactivity; the first visit may take about 30 s to wake it. |
| Storage | No database. Files written at runtime are lost on restart. |
| Localisation | UI in English; code comments in Japanese. |

## 13. Operations

| Task | How |
|---|---|
| Change a default list | Edit `templates/{COUNTRY}.csv` on GitHub (one code per line) and commit. The app redeploys in about 1–2 minutes. |
| Refresh the sector master now | GitHub → Actions → "Update Sector Master" → Run workflow. |
| Check the master date | Shown on the Sector Search page. |
| Rotate the password or API key | Streamlit Cloud → App settings → Secrets. |
| Deploy code | Merge to `main`; Streamlit Cloud redeploys automatically. |

## 14. Known limitations and open issues

Priority: **H** = affects correctness of the deliverable; **M** = affects usability or reliability; **L** = minor.

### 14.1 Data correctness

| ID | Pri | Issue | Target behaviour |
|---|---|---|---|
| DATA-1 | H | Malaysian board (Main / ACE / LEAP) is not stored in the master. The code-based rule misclassifies companies that moved from ACE to Main. | Add a `board` column to the master, taken from a maintained mapping file (`data/my_board.csv`) refreshed from Bursa's published lists. Add a board filter to Sector Search and a `Market` column to the Excel. |
| DATA-2 | H | `Market` is calculated in `extract_data` but never appears in the Excel. | Add a "Market / Board" column after "Code". |
| DATA-3 | M | The master contains ETFs, preference shares, rights and depositary receipts, alongside ordinary shares. | Exclude non-ordinary instruments by default (suffix rules plus `quoteType`), with an option to include them. |
| DATA-4 | H | Sectors follow Yahoo/Morningstar, not Bursa's or SGX's official classification. "Technology" on Yahoo is not the same set as Bursa's Technology sector. | Store the official exchange sector alongside the Yahoo sector when a reliable source is available, and let users choose which to filter by. |
| DATA-5 | H | Missing statement items are written as 0, so "no data" cannot be told apart from a true zero. | Write blank (or "N/A") for missing items. |
| DATA-6 | M | FY comes from `lastFiscalYearEnd`, while figures come from the latest balance sheet or income statement column. The two can refer to different years. | Use the statement column date as FY. |
| DATA-7 | M | The column "Debt/Equity(%)" actually holds total liabilities ÷ equity. | Rename it to "Liabilities/Equity (%)", or compute Total Debt ÷ Equity. |
| DATA-8 | M | The REVENUE column is labelled with the country currency (e.g. MYR), but the figures are in the company's reporting currency, which can differ. | Label it with the reporting currency, or convert. |
| DATA-9 | M | "Major Shareholders" usually shows Yahoo's ownership breakdown (% insiders / % institutions), not named major shareholders. | Use named holders where available, and label the source. |
| DATA-10 | L | "Closing" price date = server date − 1, which is wrong after weekends and holidays. | Use the actual date of the previous close. |
| DATA-11 | L | All FX rates are to SGD, whatever the country. | Confirm that SGD is the intended reporting base; if not, make the base selectable. |

### 14.2 Coverage

| ID | Pri | Issue | Target behaviour |
|---|---|---|---|
| COV-1 | M | No sector master for PH and VN (Yahoo screener does not cover them). Yahoo's VN data quality has not been checked. | Find an alternative list source, or document "upload only". |
| COV-2 | M | Default lists exist only for SG and MY. The MY list is a provisional Yahoo "Technology" list, not a curated IT list like SG's. | Replace it with the agreed curated MY list. |

### 14.3 Usability and reliability

| ID | Pri | Issue | Target behaviour |
|---|---|---|---|
| UX-1 | H | Results disappear on any rerun after an analysis (for example after clicking Download) and are lost if the tab closes. Long runs cannot be resumed. | Keep results in `st.session_state`; process in chunks with partial downloads; cache fetched companies (`st.cache_data`, TTL 1 day). |
| UX-2 | M | Long runs (100+ companies) take many minutes and can be throttled by Yahoo. | Fetch in parallel with limits, cache results, and show an estimated time. |
| UX-3 | M | AI Judge only outputs "Yes" companies. The full judgement list (Yes / No / Grey with reasons) cannot be downloaded for review. | Add a judgement-results download. |
| UX-4 | M | AI errors are hidden: segment failures are silent, and AI Judge batch errors appear only in Debug Mode. | Show a warning with the affected codes. |
| UX-5 | M | Compare Lists reads CSVs without keeping leading zeros, and compares codes without normalising suffixes (`0097` ≠ `0097.KL`). | Reuse `utils/codes.py` for parsing and normalisation. |
| UX-6 | L | Compare Lists and AI Judge Step 1 still call Yahoo without retry. | Use the shared retrying fetch. |

### 14.4 Operations and security

| ID | Pri | Issue | Target behaviour |
|---|---|---|---|
| SEC-1 | H | If `APP_PASSWORD` is missing, the app is fully open. | Fail closed: show an error and refuse access. |
| SEC-2 | L | One shared password, with no attempt limit and no per-user accounts. | Consider Streamlit's built-in viewer authentication (Google login) for named users. |
| OPS-1 | M | No automated tests and no CI checks on pull requests. | Add unit tests (code parsing, extract_data with fixtures) and a GitHub Actions test job. |
| OPS-2 | M | The AI Judge "Save as Default" prompt is written to disk and lost on restart. | Store the default prompt in the repository (`prompts/it_judge_prompt.txt`) and edit it on GitHub, as with default lists. |
| OPS-3 | L | `streamlit`, `pandas`, `openpyxl` and `google-genai` are unpinned, so upstream releases can break the app. | Pin tested versions. |
| OPS-4 | L | The sector master workflow fails silently if Yahoo changes its screener; the safeguard keeps old data without alerting anyone. | Fail the workflow (red) when the safeguard triggers, so GitHub sends a notification. |

## 15. Change history

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-11-23 | First specification, written after the sector master rebuild (PR #1). |
