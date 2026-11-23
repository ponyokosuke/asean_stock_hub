from .base import BaseProcessor

class MYProcessor(BaseProcessor):
    def __init__(self):
        super().__init__(currency="MYR", suffix=".KL", country="MY")

    def process_dataframe(self, df):
        df = super().process_dataframe(df)
        
        # MY特有: 必要ならここで "REVENUE MYR('000)" にしてもよい
        if "REVENUE ('000)" in df.columns:
            df = df.rename(columns={"REVENUE ('000)": "REVENUE MYR('000)"})
            
        return df