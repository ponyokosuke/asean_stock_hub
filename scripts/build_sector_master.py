"""
セクターマスタ (data/sector_master.csv) を作成するスクリプト。

Yahoo Finance のスクリーナーで「国 × セクター」ごとに全上場銘柄を取得し、
1つのCSVにまとめます。GitHub Actions から毎日実行されます。

ローカル実行:
    python scripts/build_sector_master.py
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf
from yfinance import EquityQuery

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.sector_master import COUNTRY_REGIONS, SECTORS, MASTER_PATH, META_PATH, COLUMNS

PAGE_SIZE = 250
SLEEP_SEC = 1.0
# 新しい件数が前回の半分未満なら Yahoo 側の異常とみなし、その国は前回データを残す
MIN_RATIO = 0.5
# スクリーナーに出てこない銘柄を、コード番号を直接試して補う
# (MY の LEAP Market 03001〜03199: スクリーナーは数社しか返さないが、個別には取得できる)
PROBE_CODES = {"MY": [f"03{i:03d}.KL" for i in range(1, 200)]}


def screen_all(query):
    """スクリーナーの結果をページングして全件取得"""
    quotes, offset = [], 0
    while True:
        for attempt in range(4):
            try:
                res = yf.screen(query, size=PAGE_SIZE, offset=offset,
                                sortField="intradaymarketcap", sortAsc=False)
                break
            except Exception as e:
                wait = 5 * (2 ** attempt)
                print(f"    retry in {wait}s ({e})")
                time.sleep(wait)
        else:
            raise RuntimeError("Yahoo screener failed repeatedly")

        page = res.get("quotes", [])
        quotes.extend(page)
        offset += len(page)
        time.sleep(SLEEP_SEC)
        if not page or offset >= res.get("total", 0):
            return quotes


def to_row(country, sector, q):
    return {
        "country": country,
        "symbol": q.get("symbol"),
        "name": q.get("longName") or q.get("shortName") or "",
        "sector": sector,
        "exchange": q.get("exchange", ""),
    }


def build_country(country, region):
    rows, seen = [], set()
    for sector in SECTORS:
        q = EquityQuery("and", [EquityQuery("eq", ["region", region]),
                                EquityQuery("eq", ["sector", sector])])
        hits = screen_all(q)
        print(f"  {country} {sector}: {len(hits)}")
        for h in hits:
            if h.get("symbol") and h["symbol"] not in seen:
                seen.add(h["symbol"])
                rows.append(to_row(country, sector, h))

    # セクター未分類の銘柄も "Unknown" として残す
    for h in screen_all(EquityQuery("eq", ["region", region])):
        if h.get("symbol") and h["symbol"] not in seen:
            seen.add(h["symbol"])
            rows.append(to_row(country, "Unknown", h))

    rows += probe_codes(country, PROBE_CODES.get(country, []), seen)
    return rows


def probe_codes(country, codes, seen):
    """スクリーナーに無いコードを直接取得し、直近2年に株価がある銘柄を追加"""
    codes = [c for c in codes if c not in seen]
    if not codes:
        return []
    close = yf.download(codes, period="2y", progress=False, threads=True)["Close"]
    alive = [c for c in codes if c in close and close[c].notna().any()]
    rows = []
    for code in alive:
        info = {}
        for attempt in range(3):
            try:
                info = yf.Ticker(code).info
                break
            except Exception as e:
                print(f"    retry {code} ({e})")
                time.sleep(5 * (2 ** attempt))
        seen.add(code)
        rows.append({
            "country": country,
            "symbol": code,
            "name": info.get("longName") or info.get("shortName") or "",
            "sector": info.get("sector") if info.get("sector") in SECTORS else "Unknown",
            "exchange": info.get("exchange", ""),
        })
        time.sleep(SLEEP_SEC)
    print(f"  {country} probed: {len(rows)} added")
    return rows


def main():
    old = pd.read_csv(MASTER_PATH, dtype=str) if os.path.exists(MASTER_PATH) else pd.DataFrame(columns=COLUMNS)

    frames = []
    for country, region in COUNTRY_REGIONS.items():
        print(f"[{country}] region={region}")
        try:
            new = pd.DataFrame(build_country(country, region), columns=COLUMNS)
        except Exception as e:
            print(f"  ERROR: {e}")
            new = pd.DataFrame(columns=COLUMNS)

        prev = old[old["country"] == country]
        if len(new) < len(prev) * MIN_RATIO:
            print(f"  WARNING: {len(new)} rows vs {len(prev)} before. Keeping previous data.")
            new = prev
        frames.append(new)

    master = pd.concat(frames, ignore_index=True)
    # タイの NVDR (-R) / 外国人枠 (-F) は本体と重複するので除外
    master = master[~master["symbol"].str.contains(r"-[RF]\.BK$", regex=True)]
    # ETF は企業ではないので除外 (MY は "xxxxEA.KL"、他は名称に "ETF" を含むもの)
    is_etf = (master["symbol"].str.contains(r"^\d{4}EA\.KL$", regex=True)
              | master["name"].str.contains(r"\bETF\b", case=False, regex=True))
    master = master[~is_etf]
    master = master.sort_values(["country", "sector", "symbol"]).reset_index(drop=True)

    csv_text = master.to_csv(index=False)
    if os.path.exists(MASTER_PATH):
        with open(MASTER_PATH, encoding="utf-8") as f:
            if f.read() == csv_text:
                print("No changes.")
                return

    os.makedirs(os.path.dirname(MASTER_PATH), exist_ok=True)
    with open(MASTER_PATH, "w", encoding="utf-8") as f:
        f.write(csv_text)
    meta = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "counts": master.groupby("country").size().to_dict(),
    }
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Saved {len(master)} rows -> {MASTER_PATH}")


if __name__ == "__main__":
    main()
