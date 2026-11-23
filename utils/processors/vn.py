from .base import BaseProcessor

class VNProcessor(BaseProcessor):
    def __init__(self):
        super().__init__(currency="VND", suffix=".VN", country="VN")

    def process_dataframe(self, df):
        # 親の処理を呼ぶ前に、独自に計算しても良いが、一旦親を呼ぶ
        df = super().process_dataframe(df)
        
        # VN特有: リネーム
        if "REVENUE ('000)" in df.columns:
            df = df.rename(columns={"REVENUE ('000)": "REVENUE VND('000)"})
            
        return df