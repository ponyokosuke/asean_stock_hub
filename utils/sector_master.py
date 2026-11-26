import json
import os
import re

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_PATH = os.path.join(BASE_DIR, "data", "sector_master.csv")
META_PATH = os.path.join(BASE_DIR, "data", "sector_master_meta.json")
# 取引所の公式分類 (市場区分・公式セクター)。保守担当が利用許諾のある情報源から手動で更新する
OFFICIAL_DIR = os.path.join(BASE_DIR, "data", "official")
OFFICIAL_COLUMNS = ["symbol", "name", "board", "official_sector", "official_industry"]

COLUMNS = ["country", "symbol", "name", "sector", "exchange"]

# アプリの国コード -> Yahoo スクリーナーの region
# ※ PH / VN は Yahoo スクリーナーが対応していないため対象外 (CSVアップロードで対応)
COUNTRY_REGIONS = {
    "SG": "sg",
    "MY": "my",
    "TH": "th",
    "ID": "id",
}

SECTORS = [
    "Basic Materials",
    "Communication Services",
    "Consumer Cyclical",
    "Consumer Defensive",
    "Energy",
    "Financial Services",
    "Healthcare",
    "Industrials",
    "Real Estate",
    "Technology",
    "Utilities",
]


def my_board_from_code(symbol):
    """Bursa のコード体系から市場区分を推定する。

    03xxx は LEAP、1〜9 で始まる4桁は Main で確定。
    0xxx は ACE が基本だが、ACE→Main に移った会社もコードが変わらないため確定できない。
    """
    code = symbol.upper().removesuffix(".KL")
    if re.fullmatch(r"03\d{3}", code):
        return "LEAP"
    if re.fullmatch(r"[1-9]\d{3}", code):
        return "Main"
    if re.fullmatch(r"0\d{3}", code):
        return "ACE (unverified)"
    return "Other"


# {country: (ファイル更新時刻, データ)}。ファイルが更新されたら読み直す
_official_cache = {}


def load_official(country):
    """data/official/{country}.csv を {symbol: {board, official_sector, official_industry}} で返す"""
    path = os.path.join(OFFICIAL_DIR, f"{country}.csv")
    if not os.path.exists(path):
        return {}
    mtime = os.path.getmtime(path)
    cached = _official_cache.get(country)
    if cached and cached[0] == mtime:
        return cached[1]
    df = pd.read_csv(path, dtype=str).fillna("")
    df = df.reindex(columns=OFFICIAL_COLUMNS, fill_value="")
    df["symbol"] = df["symbol"].str.strip().str.upper()
    data = df.set_index("symbol").to_dict("index")
    _official_cache[country] = (mtime, data)
    return data


def classify(country, symbol):
    """市場区分と公式セクターを返す。公式ファイルを優先し、無ければコードから推定 (MYのみ)"""
    official = load_official(country).get(symbol.upper(), {})
    board = official.get("board", "")
    if not board and country == "MY":
        board = my_board_from_code(symbol)
    return {
        "board": board,
        "official_sector": official.get("official_sector", ""),
        "official_industry": official.get("official_industry", ""),
    }


def load_master():
    """セクターマスタを読み込み、市場区分・公式セクターの列を付ける (無ければ空のDataFrame)"""
    if not os.path.exists(MASTER_PATH):
        return pd.DataFrame(columns=COLUMNS + ["board", "official_sector", "official_industry"])
    df = pd.read_csv(MASTER_PATH, dtype=str).fillna("")
    extra = pd.DataFrame([classify(c, s) for c, s in zip(df["country"], df["symbol"])], index=df.index)
    return pd.concat([df, extra], axis=1)


def load_meta():
    if not os.path.exists(META_PATH):
        return {}
    with open(META_PATH, encoding="utf-8") as f:
        return json.load(f)
