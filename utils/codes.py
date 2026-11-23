import re

import pandas as pd

# "1155", "0097.KL", "D05.SI", "CHARAN.BK" など。ヘッダー行 ("Stock Code" 等) は除外される
CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,11}(\.[A-Z]{1,3})?$")
HEADER_WORDS = {"CODE", "CODES", "SYMBOL", "TICKER", "STOCK"}


def parse_codes(source, suffix=""):
    """CSV (パス or アップロードファイル) の1列目から銘柄コードを読み込む。

    - 空ファイルでもエラーにせず [] を返す
    - 空白除去・重複除去 (順序は保持)
    - サフィックスが無いコードには国のサフィックスを付与
    """
    try:
        df = pd.read_csv(source, header=None, dtype=str)
    except pd.errors.EmptyDataError:
        return []

    codes = []
    for raw in df[0].dropna():
        code = str(raw).strip().upper()
        if not CODE_PATTERN.match(code) or code in HEADER_WORDS:
            continue
        if "." not in code and suffix:
            code += suffix
        if code not in codes:
            codes.append(code)
    return codes
