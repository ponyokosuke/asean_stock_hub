import time
from datetime import datetime

import pandas as pd
import streamlit as st

from utils.processors import get_processor


class FetchError(Exception):
    pass


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def fetch_company(country_code, code):
    """1社分のデータを取得して1行に整形する。

    成功した結果は1日キャッシュされるので、途中でタブを閉じても再実行すれば続きから速く進む。
    失敗は例外にしてキャッシュさせない (次回また取りに行く)。
    """
    processor = get_processor(country_code)
    raw = processor.get_stock_data(code)
    if not raw:
        raise FetchError(code)
    return processor.extract_data(code, raw)


def _result_key(file_prefix, country_code):
    return f"result_{file_prefix}_{country_code}"


def run_financial_analysis(codes, processor, country_code, file_prefix, extra_fields=None):
    """Version 1 と同じ財務データ取得 → AI分析 → Excel出力 (V1/V2/V3 共通)

    結果は st.session_state に保存し、show_result() で表示する
    (ダウンロードボタン等で再実行されても結果が消えないように)。
    extra_fields: {code: {列名: 値}} で各銘柄の行に値を上書きできる
    """
    key = _result_key(file_prefix, country_code)
    st.session_state.pop(key, None)

    status_text = st.empty()
    progress_bar = st.progress(0)

    all_results, failed, cached = [], [], 0
    total = len(codes)
    for i, code in enumerate(codes):
        status_text.text(f"Fetching Financial Data ({i+1}/{total}): {code}...")
        progress_bar.progress((i + 1) / (total + 1))

        start = time.time()
        try:
            data = dict(fetch_company(country_code, code))
        except FetchError:
            # データが無くてもリストから消えないよう、社名・市場区分だけの行を残す
            failed.append(code)
            all_results.append(processor.no_data_row(code))
            continue
        # 市場区分・公式分類はキャッシュせず、最新の data/official から付け直す
        data.update(processor.classification_fields(code))
        if extra_fields and code in extra_fields:
            data.update(extra_fields[code])
        all_results.append(data)

        # キャッシュから即返った場合は待たない
        if time.time() - start < 0.05:
            cached += 1
        else:
            time.sleep(0.3)

    progress_bar.empty()
    status_text.empty()

    if len(failed) == total:
        st.session_state[key] = {"failed": failed, "total": total, "excel": None}
        return

    with st.spinner("🤖 Running AI Analysis..."):
        all_results = processor.run_ai_analysis(all_results)

    df = processor.process_dataframe(pd.DataFrame(all_results))
    excel_data = processor.generate_excel_binary(df)

    st.session_state[key] = {
        "excel": excel_data,
        "df": df,
        "failed": failed,
        "cached": cached,
        "total": total,
        "file_name": f"{file_prefix}_{country_code}_{datetime.today().strftime('%Y-%m-%d')}.xlsx",
        "finished_at": datetime.now().strftime("%H:%M"),
    }


def show_result(file_prefix, country_code):
    """直近の分析結果 (このセッション内) を表示する"""
    result = st.session_state.get(_result_key(file_prefix, country_code))
    if not result:
        return

    st.divider()
    if result["failed"]:
        st.warning(f"⚠️ No Yahoo Finance data for {len(result['failed'])} code(s): {', '.join(result['failed'])}. "
                   "They are kept in the Excel with the remark \"No data on Yahoo Finance\" and blank figures.")

    if result["excel"] is None:
        st.error("No data retrieved. Yahoo Finance may be limiting requests — please wait a few minutes and try again. "
                 "Companies already fetched are cached, so a retry continues quickly.")
        return

    done = result["total"] - len(result["failed"])
    note = f" · {result['cached']} from cache" if result.get("cached") else ""
    st.success(f"✅ Completed at {result['finished_at']} ({done}/{result['total']} companies{note})")

    st.download_button(
        label="📥 Download Excel File",
        data=result["excel"],
        file_name=result["file_name"],
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        on_click="ignore",
    )
    st.subheader("Preview")
    st.dataframe(result["df"])
