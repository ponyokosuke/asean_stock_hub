import time
from datetime import datetime

import pandas as pd
import streamlit as st


def run_financial_analysis(codes, processor, country_code, file_prefix, extra_fields=None):
    """Version 1 と同じ財務データ取得 → AI分析 → Excel出力 (V1/V2/V3 共通)

    extra_fields: {code: {列名: 値}} で各銘柄の行に値を上書きできる
    """
    status_text = st.empty()
    progress_bar = st.progress(0)

    all_results, failed = [], []
    total = len(codes)
    for i, code in enumerate(codes):
        status_text.text(f"Fetching Financial Data ({i+1}/{total}): {code}...")
        progress_bar.progress((i + 1) / (total + 1))

        raw = processor.get_stock_data(code)
        if raw:
            data = processor.extract_data(code, raw)
            if extra_fields and code in extra_fields:
                data.update(extra_fields[code])
            all_results.append(data)
        else:
            failed.append(code)
        time.sleep(0.3)

    if failed:
        st.warning(f"⚠️ Could not retrieve data for {len(failed)} code(s): {', '.join(failed)}")

    if not all_results:
        status_text.empty()
        st.error("No data retrieved. Yahoo Finance may be limiting requests — please wait a few minutes and try again.")
        return

    status_text.text("🤖 Running AI Analysis...")
    all_results = processor.run_ai_analysis(all_results)

    status_text.text("📏 Formatting data...")
    df = processor.process_dataframe(pd.DataFrame(all_results))
    excel_data = processor.generate_excel_binary(df)

    progress_bar.progress(100)
    status_text.success(f"✅ All processes completed! ({len(all_results)}/{total} companies)")

    st.download_button(
        label="📥 Download Excel File",
        data=excel_data,
        file_name=f"{file_prefix}_{country_code}_{datetime.today().strftime('%Y-%m-%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.subheader("Preview")
    st.dataframe(df)
