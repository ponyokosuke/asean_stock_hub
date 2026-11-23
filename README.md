# 🌏 ASEAN Stock Analysis Hub

ASEAN（東南アジア）市場の株式を分析するための Streamlit アプリケーションです。
国ごとの通貨や市場ルールの違いを吸収し、財務データの取得、セクター検索、AIによる事業判定を一元管理します。

## 📂 ディレクトリ構成とファイルの役割

### 🏠 ルートディレクトリ
- **`Home.py`**
  - アプリの玄関口（エントリーポイント）。
  - 全体の設定や、対象国（シンガポール、マレーシアなど）の選択状態を管理します。
- **`requirements.txt`**
  - 必要なPythonライブラリの一覧（`pip install -r requirements.txt` で使用）。
- **`.env`**
  - ローカル環境用のAPIキー設定ファイル（Gemini APIキーなどを記述）。
- **`.streamlit/secrets.toml`**
  - Streamlit Community Cloud（デプロイ先）用の機密情報設定ファイル。

### 📄 pages/（機能ごとの画面）
サイドバーのメニューに対応する各ツールの画面です。
- **`00_User_Guide.py`**
  - `docs/USER_GUIDE.md`（英語の初心者向け使い方ガイド、画像は `docs/images/`）をアプリ内に表示します。
- **`01_Financial_Data.py`**
  - **旧 Version 1**: 銘柄リスト（CSV）を読み込み、Yahoo Financeから財務データを取得してエクセル化します。
  - AIによる事業セグメント分析機能も含みます。
- **`02_Sector_Search.py`**
  - **旧 Version 2**: 「不動産」「テクノロジー」などのセクターを指定して、条件に合う銘柄をスクリーニングします。
- **`03_AI_Judge.py`**
  - **旧 Version 3**: 企業の事業概要をAI（Gemini）に読ませ、「IT企業か？」などの特定条件判定を行います。
- **`04_Compare_Lists.py`**
  - 2つの銘柄リスト（CSV）を比較し、新規追加・削除された銘柄を特定するツールです。
- **`05_Specification.py`**
  - `docs/SPECIFICATION.md`（英語の仕様書）をアプリ内に表示します。

### 🛠 utils/（裏方のロジック）
画面には表示されない、計算やデータ処理を行うプログラム群です。
- **`ui.py`**
  - サイドバーに「国選択メニュー」を表示する共通部品。全ページから呼び出されます。
- **`sector_master.py`**
  - セクターマスタ（`data/sector_master.csv`）の読み込みと、対象国・セクターの定義。
- **`codes.py`**
  - CSVから銘柄コードを読み込む共通処理（空ファイル・ヘッダー・重複・先頭ゼロに対応）。
- **`analysis.py`**
  - 財務データ取得 → AI分析 → Excel出力の共通処理（Version 1 / 2 / 3 で共用）。

### 🗂 data/ と templates/
- **`data/sector_master.csv`**
  - SG / MY / TH / ID の全上場銘柄とセクターの一覧。Sector Search と AI Judge はこれを使います。
  - `.github/workflows/update_sector_master.yml` が毎日 06:00 (SGT) に `scripts/build_sector_master.py` を実行し、変更があればコミットします（Actions 画面から手動実行も可能）。
  - PH / VN は Yahoo のスクリーナー非対応のため対象外です（Version 1 のCSVアップロードで対応）。
- **`templates/{国コード}.csv`**
  - Version 1 の「デフォルトリスト」。1行1銘柄コード。
  - Streamlit Cloud 上で保存したファイルは再起動で消えるため、変更は GitHub 上でこのファイルを編集してください。

#### utils/processors/（国ごとの処理切り替え）
「Strategyパターン」を使用して、国ごとの処理の違い（通貨、税率、計算式など）を吸収しています。
- **`__init__.py`**
  - 選択された国コード（SG, MYなど）に応じて、適切な担当者クラス（Processor）を呼び出す工場（Factory）の役割。
- **`base.py`** (親クラス)
  - 全国共通のロジック（Yahoo Financeへのアクセス、AI分析の基本プロンプトなど）が記述されています。
- **`sg.py`** (子クラス)
  - **シンガポール専用**。通貨をSGDに変換したり、SG特有のエクセル整形ルールを記述します。
- **`my.py`** (子クラス)
  - **マレーシア専用**。通貨をMYRに変換する処理などを記述します。
- **`vn.py`** (子クラス)
  - **ベトナム専用**。桁数が大きいため単位調整を行うなどの処理を記述します。

## 🚀 セットアップ手順

1. ライブラリのインストール
   ```bash
   pip install -r requirements.txt