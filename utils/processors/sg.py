from .base import BaseProcessor

class SGProcessor(BaseProcessor):
    def __init__(self):
        # シンガポール設定 (通貨: SGD, サフィックス: .SI)
        super().__init__(currency="SGD", suffix=".SI", country="SG")

    def process_dataframe(self, df):
        # 1. Baseの共通処理を行う (単位変換など)
        df = super().process_dataframe(df)
        
        # 2. SG特有: Revenueの列名を "REVENUE SGD('000)" に変更
        if "REVENUE ('000)" in df.columns:
            df = df.rename(columns={"REVENUE ('000)": "REVENUE SGD('000)"})
            
        return df