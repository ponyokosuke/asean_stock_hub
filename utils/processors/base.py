import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time
import json
import io
import os
from google import genai
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from dotenv import load_dotenv
from utils.sector_master import classify, load_official

# Excel の「公式分類」列に使う取引所名
EXCHANGE_LABELS = {"SG": "SGX", "MY": "Bursa", "TH": "SET", "ID": "IDX", "PH": "PSE", "VN": "HOSE"}

# クラス内でも確実に読み込む
load_dotenv()

class BaseProcessor:
    def __init__(self, currency="USD", suffix="", country=""):
        self.currency = currency
        self.suffix = suffix
        self.country = country
        self.exchange_label = EXCHANGE_LABELS.get(country, "SGX")
        
        # APIキーの取得とクライアント初期化
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Client Init Error: {e}")

    # --- 1. データ取得 (Yahoo Finance) ---
    def get_stock_data(self, code, retries=3):
        try:
            ticker = yf.Ticker(code)
            info = None
            # Yahoo のレート制限対策: 失敗したら待って再試行 (2s, 4s, 8s)
            for attempt in range(retries + 1):
                try:
                    info = ticker.info
                    break
                except Exception as e:
                    if attempt == retries:
                        print(f"  info取得失敗 {code}: {e}")
                        return None
                    time.sleep(2 * (2 ** attempt))

            # 存在しないコードでも Yahoo はほぼ空の info を返すので、社名が無ければデータ無しとする
            if not info or not (info.get('longName') or info.get('shortName')): return None

            return {
                "info": info,
                "balance_sheet": ticker.balance_sheet,
                "financials": ticker.financials,
                "major_holders": ticker.major_holders,
                "institutional_holders": ticker.institutional_holders
            }
        except Exception as e:
            print(f"  データ取得エラー: {e}")
            return None

    # --- 2. 為替レート取得 (前日終値優先) ---
    def get_exchange_rate(self, from_currency):
        if not from_currency or from_currency == "SGD": # 基本はSGD基準
            return 1.0
        
        currency_code = "CNY" if from_currency == "RMB (CNY)" else from_currency
        pair = f"{currency_code}SGD=X" # SGDへの変換レート
        
        try:
            ticker = yf.Ticker(pair)
            rate = ticker.info.get('previousClose')
            if rate is None:
                hist = ticker.history(period="5d")
                if not hist.empty:
                    rate = hist['Close'].iloc[-1]
                else:
                    return "N/A"
            return rate
        except:
            return "N/A"

    # --- 3. データ抽出 (extract_data 完全再現) ---
    def extract_data(self, code, raw_data):
        info = raw_data.get("info", {})
        bs = raw_data.get("balance_sheet")
        inc = raw_data.get("financials")
        major_holders = raw_data.get("major_holders")
        inst_holders = raw_data.get("institutional_holders")

        # 株主情報の整形
        def format_shareholders(holders_data, data_type="institutional"):
            if holders_data is None or holders_data.empty: return None
            result_lines = []
            try:
                if data_type in ["institutional", "insider"]:
                    name_col = next((c for c in holders_data.columns if "holder" in str(c).lower() or "insider" in str(c).lower()), None)
                    pct_col = next((c for c in holders_data.columns if "%" in str(c).lower() or "pct" in str(c).lower()), None)
                    if name_col and pct_col:
                        for _, row in holders_data.head(10).iterrows():
                            val = row[pct_col]
                            val_str = f"{float(val)*100:.2f}%" if isinstance(val, (int, float)) and val < 1 else str(val)
                            result_lines.append(f"{row[name_col]}: {val_str}")
                elif data_type == "major":
                    if len(holders_data.columns) == 1:
                        for idx, row in holders_data.head(5).iterrows():
                            val = row.iloc[0]
                            desc = str(idx)
                            result_lines.append(f"{desc}: {val}")
                    elif len(holders_data.columns) >= 2:
                        for _, row in holders_data.head(5).iterrows():
                            # 値と説明が逆の場合の対応
                            v, d = row.iloc[0], row.iloc[1]
                            name = str(d) if len(str(d)) > len(str(v)) else str(v)
                            val = str(v) if len(str(d)) > len(str(v)) else str(d)
                            result_lines.append(f"{name}: {val}")
            except: pass
            return "\n".join(result_lines) if result_lines else None

        shareholder_text = format_shareholders(major_holders, "major")
        if not shareholder_text:
            shareholder_text = format_shareholders(inst_holders, "institutional") or "Not Available"

        # 最新日付の特定
        latest_date = None
        if bs is not None and not bs.empty: latest_date = bs.columns[0]
        elif inc is not None and not inc.empty: latest_date = inc.columns[0]

        # 取得できない項目は None (Excel では空欄) にする。0 は「本当にゼロ」の場合だけ
        def get_fin_value(df, key):
            if df is not None and not df.empty and key in df.index and latest_date in df.columns:
                val = df.loc[key, latest_date]
                if not pd.isna(val):
                    return float(val)
            return None

        def first_value(*vals):
            return next((v for v in vals if v is not None), None)

        # 財務数値取得
        revenue = get_fin_value(inc, "Total Revenue")
        ope_inc = get_fin_value(inc, "Operating Income")
        profit = first_value(get_fin_value(inc, "Pretax Income"), ope_inc)
        
        net_owners = first_value(get_fin_value(inc, "Net Income"),
                                 get_fin_value(inc, "Net Income Common Stock"))
        net_group = first_value(get_fin_value(inc, "Net Income Including Noncontrolling Interests"),
                                get_fin_value(inc, "Net Income Continuous Operations"),
                                net_owners)

        minority = get_fin_value(bs, "Minority Interest")
        stock_eq = get_fin_value(bs, "Stockholders Equity")
        total_assets = get_fin_value(bs, "Total Assets")
        total_eq = get_fin_value(bs, "Total Equity Gross Minority Interest")
        if total_eq is None and stock_eq is not None:
            total_eq = stock_eq + (minority or 0)

        loan = get_fin_value(bs, "Total Debt")
        if loan is None:
            cur_debt, lt_debt = get_fin_value(bs, "Current Debt"), get_fin_value(bs, "Long Term Debt")
            if cur_debt is not None or lt_debt is not None:
                loan = (cur_debt or 0) + (lt_debt or 0)

        # 比率計算 (分母が無い・ゼロなら空欄)
        de_ratio = (total_assets - total_eq) / total_eq if (total_eq and total_assets is not None) else None
        le_ratio = loan / total_eq if (total_eq and loan is not None) else None

        # FY Date
        fy_date = None
        if info.get('lastFiscalYearEnd'):
            try: fy_date = datetime.fromtimestamp(info['lastFiscalYearEnd'])
            except: pass

        # 役員
        officers = info.get('companyOfficers', [])
        top_exec = "N/A"
        if officers:
            for o in officers:
                t = o.get('title', '').lower()
                if 'ceo' in t or 'chairman' in t:
                    top_exec = f"{o.get('name')} ({o.get('title')})"
                    break
            if top_exec == "N/A" and len(officers) > 0: top_exec = officers[0].get('name')

        # 通貨・レート
        raw_cur = info.get('financialCurrency') or info.get('currency', 'SGD')
        disp_cur = 'RMB (CNY)' if raw_cur == 'CNY' else raw_cur
        exchange_rate = self.get_exchange_rate(disp_cur)

        # 株価 (前日終値優先)
        curr_price = info.get('previousClose') or info.get('regularMarketPrice')
        shares = info.get('sharesOutstanding')
        mcap = (curr_price * shares) if (curr_price and shares) else info.get('marketCap')

        return {
            "Name of Company": info.get('longName'),
            "Code": code,
            "Currency": disp_cur,
            "Exchange Rate": exchange_rate,
            "Website": info.get('website', ''),
            "Major Shareholders": shareholder_text,
            "FY": fy_date,
            "REVENUE": revenue,
            "Segments": "",
            "PROFIT": profit,
            "GROSS PROFIT": get_fin_value(inc, "Gross Profit"),
            "OPERATING PROFIT": ope_inc,
            "NET PROFIT (Group)": net_group,
            "NET PROFIT (Shareholders)": net_owners,
            "Minority Interest": minority,
            "Shareholders' Equity": stock_eq,
            "Total Equity": total_eq,
            "TOTAL ASSET": total_assets,
            "Debt/Equity(%)": de_ratio,
            "Loan": loan,
            "Loan/Equity (%)": le_ratio,
            "Stock Price": curr_price,
            "Shares Outstanding": shares,
            "Market Cap": mcap,
            "Summary of Business": info.get('longBusinessSummary', ''),
            "Chairman / CEO": top_exec,
            "Address": f"{info.get('address1','')}, {info.get('address2','')}, {info.get('city','')}, {info.get('country','')} {info.get('zip','')}",
            "Contact No.": info.get('phone'),
            "Number of Employee Current": info.get('fullTimeEmployees'),
            "Category Classification/YahooFin": info.get('sector', "Not Available"),
            "Sector & Industry/YahooFin": info.get('industry', "Not Available"),
            **self.classification_fields(code),
        }

    # --- 4. AI分析 (Batch Analyze 完全再現) ---
    def classification_fields(self, code):
        """市場区分・公式分類の列 (data/official 優先、MY はコードから推定)。

        取得データのキャッシュとは別に毎回計算するので、公式ファイルの修正がすぐ反映される。
        """
        official = classify(self.country, str(code))
        return {
            "Market / Board": official["board"],
            f"Category Classification/{self.exchange_label}": official["official_sector"],
            f"Sector & Industry/ {self.exchange_label}": official["official_industry"],
        }

    def no_data_row(self, code):
        """Yahoo にデータが無い銘柄の行。社名・市場区分だけ入れて、財務の列は空欄にする"""
        name = load_official(self.country).get(str(code).upper(), {}).get("name", "")
        return {
            "Name of Company": name,
            "Code": code,
            "Remarks": "No data on Yahoo Finance",
            **self.classification_fields(code),
        }

    def run_ai_analysis(self, all_results):
        if not self.client:
            print("⚠️ API Key not found. Skipping AI analysis.")
            return all_results
        
        targets = [x for x in all_results if x.get('Summary of Business')]
        if not targets: return all_results

        print(f"🤖 Gemini AI分析開始: 対象 {len(targets)} 件...")
        batch_size = 20
        
        for i in range(0, len(targets), batch_size):
            batch = targets[i : i + batch_size]
            input_text = ""
            for item in batch:
                summary = str(item['Summary of Business'])[:500].replace("\n", " ")
                input_text += f"Code: {item['Code']}\nSummary: {summary}...\n---\n"

            prompt = f"""
            You are a financial analyst. I will provide business summaries for multiple companies.
            Extract the main 'Business Segments' for EACH company based on the summary.

            # Input Data
            {input_text}
            
            # Output Rules
            - Return ONLY a valid JSON object.
            - The keys must be the stock 'Code'.
            - The values must be the 'Business Segments' (comma separated string, clear and concise).
            - If segments are not clearly stated, summarize the main business areas in 3-4 words.
            - Example JSON Format:
            {{
                "4863.KL": "Telecommunication Services, Digital Solutions",
                "0021.KL": "Payment Services, Solution Services"
            }}
            """
            try:
                resp = self.client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                text = resp.text.replace("```json", "").replace("```", "").strip()
                seg_map = json.loads(text)
                for item in batch:
                    if item['Code'] in seg_map:
                        item['Segments'] = seg_map[item['Code']]
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ Batch Error: {e}")
        
        return all_results

    # --- 5. エクセル整形 (format_for_excel 相当) ---
    def process_dataframe(self, df):
        # 数値の単位変換 ('000)
        money_cols = [
            'REVENUE', 'PROFIT', 'GROSS PROFIT', 'OPERATING PROFIT', 
            'NET PROFIT (Group)', 'NET PROFIT (Shareholders)',
            'Minority Interest', "Shareholders' Equity", 'Total Equity', 'TOTAL ASSET',
            'Loan', 'Market Cap', 'Shares Outstanding'
        ]
        
        for col in money_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce') / 1000.0

        # パーセント列
        for col in ["Debt/Equity(%)", "Loan/Equity (%)"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # リネーム
        df = df.rename(columns={c: f"{c} ('000)" for c in money_cols})
        
        # FY日付整形
        if 'FY' in df.columns:
            df['FY'] = pd.to_datetime(df['FY'], errors='coerce').dt.strftime('%b %Y').fillna('')

        return df

    # --- 6. Excelバイナリ生成 (main.py の保存ロジック完全再現) ---
    def generate_excel_binary(self, df):
        # 不要列削除
        if "Sector /Industry" in df.columns: df = df.drop(columns=["Sector /Industry"])
        
        # 重複削除
        df = df.loc[:, ~df.columns.duplicated()]

        # Ref追加
        df["Ref"] = range(1, len(df) + 1)
        
        # 空列の追加 (順序保持のため)
        empty_cols = [
            "Taka's comments", "Remarks", "Visited (V) / Meeting Proposal (MP)",
            "Access", "Last Communications", "Category Classification/\nShareInvestor", 
            "Incorporated\n (IN / Year)"
        ]
        for col in empty_cols:
            df[col] = df[col].fillna("") if col in df.columns else ""
        
        df["Listed 'o' / Non Listed \"x\""] = "o"

        # ★日付計算 (前日)
        yesterday = datetime.now() - timedelta(days=1)
        yesterday_str = yesterday.strftime("%b %d")

        # 列名変更 (日付付き)
        final_stock_col = f"Stock Price ({yesterday_str}, Closing)"
        final_rate_col = f"Exchange Rate (to SGD) ({yesterday_str}, Closing)"
        
        rename_map = {}
        if "Stock Price" in df.columns: rename_map["Stock Price"] = final_stock_col
        if "Exchange Rate" in df.columns: rename_map["Exchange Rate"] = final_rate_col
        if "Number of Employee" in df.columns: rename_map["Number of Employee"] = "Number of Employee Current"
        
        df = df.rename(columns=rename_map)

        # ★最終的な列順序 (main.py と完全に同じ)
        target_order = [
            "Ref", "Name of Company", "Code", "Market / Board", "Listed 'o' / Non Listed \"x\"",
            "Taka's comments", "Remarks", "Visited (V) / Meeting Proposal (MP)",
            "Website", "Major Shareholders", "Currency", 
            final_rate_col, 
            "FY", 
            # REVENUEは子クラスでリネームされる可能性があるため動的に探す
            next((c for c in df.columns if "REVENUE" in c), "REVENUE ('000)"),
            "Segments", "PROFIT ('000)", "GROSS PROFIT ('000)", "OPERATING PROFIT ('000)",
            "NET PROFIT (Group) ('000)", "NET PROFIT (Shareholders) ('000)", 
            "Minority Interest ('000)", "Shareholders' Equity ('000)",
            "Total Equity ('000)", "TOTAL ASSET ('000)", "Debt/Equity(%)",
            "Loan ('000)", "Loan/Equity (%)",
            final_stock_col,
            "Shares Outstanding ('000)", "Market Cap ('000)",
            "Summary of Business", "Chairman / CEO", "Address", "Contact No.", 
            "Access", "Last Communications", "Number of Employee Current",
            "Category Classification/YahooFin", "Sector & Industry/YahooFin", 
            "Category Classification/\nShareInvestor", "Incorporated\n (IN / Year)",
            f"Category Classification/{self.exchange_label}", f"Sector & Industry/ {self.exchange_label}"
        ]

        # 存在しない列は空文字で埋める
        for col in target_order:
            if col not in df.columns: df[col] = ""
        
        # 並び替え
        df = df.reindex(columns=target_order)

        # バイナリへ保存 & スタイリング
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        
        output.seek(0)
        wb = load_workbook(output)
        ws = wb.active
        
        # スタイル定義 (main.py 再現)
        header_fill = PatternFill(start_color="fefe99", end_color="fefe99", fill_type="solid")
        header_font = Font(bold=True)
        right_align = Alignment(horizontal='right')

        for cell in ws[1]:
            col_name = str(cell.value)
            col_idx = cell.column
            cell.fill = header_fill
            cell.font = header_font
            
            number_format = None
            apply_alignment = False
            
            if "('000)" in col_name:
                number_format = '#,##0;(#,##0)'
                apply_alignment = True
            elif "(%)" in col_name or "%" in col_name:
                number_format = '0.00%'
                apply_alignment = True
            elif col_name == "FY":
                apply_alignment = True
            elif "Stock Price" in col_name:
                number_format = '#,##0.000'
                apply_alignment = True
            elif "Exchange Rate" in col_name:
                number_format = '0.0000'
                apply_alignment = True
            
            # 列全体に適用
            if number_format or apply_alignment:
                for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
                    for cell_data in row:
                        if apply_alignment: cell_data.alignment = right_align
                        if number_format: cell_data.number_format = number_format
        
        final_out = io.BytesIO()
        wb.save(final_out)
        return final_out.getvalue()