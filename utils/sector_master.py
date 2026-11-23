import json
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_PATH = os.path.join(BASE_DIR, "data", "sector_master.csv")
META_PATH = os.path.join(BASE_DIR, "data", "sector_master_meta.json")

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


def load_master():
    """セクターマスタを読み込む (無ければ空のDataFrame)"""
    if not os.path.exists(MASTER_PATH):
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(MASTER_PATH, dtype=str).fillna("")


def load_meta():
    if not os.path.exists(META_PATH):
        return {}
    with open(META_PATH, encoding="utf-8") as f:
        return json.load(f)
