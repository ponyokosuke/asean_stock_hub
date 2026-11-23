from .base import BaseProcessor
from .sg import SGProcessor
from .my import MYProcessor
from .vn import VNProcessor

def get_processor(country_code):
    if country_code == "SG":
        return SGProcessor()
    elif country_code == "MY":
        return MYProcessor()
    elif country_code == "VN":
        return VNProcessor()
    elif country_code == "TH":
        return BaseProcessor(currency="THB", suffix=".BK", country="TH")
    elif country_code == "ID":
        return BaseProcessor(currency="IDR", suffix=".JK", country="ID")
    elif country_code == "PH":
        return BaseProcessor(currency="PHP", suffix=".PS", country="PH")
    else:
        # デフォルトはBase (USD扱いなど)
        return BaseProcessor(currency="USD", suffix="")
