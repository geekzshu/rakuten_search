import streamlit as st
import pandas as pd
import time
import os
from dotenv import load_dotenv
from rakuten_competitor_analysis import RakutenCompetitorAnalysis
from rakuten_item_details import RakutenItemDetails
from rakuten_js_item_details import RakutenJSItemDetails

# .envファイルの内容を読み込見込む
load_dotenv()

# ページ設定
st.set_page_config(
    page_title="楽天商品情報取得ツール",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSSスタイル
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #bf0000;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.8rem;
        color: #444;
        margin-bottom: 1rem;
    }
    .info-text {
        font-size: 1rem;
        color: #666;
    }
    .success-box {
        padding: 1rem;
        background-color: #e6ffe6;
        border-left: 5px solid #00cc00;
        margin-bottom: 1rem;
    }
    .warning-box {
        padding: 1rem;
        background-color: #fff3e6;
        border-left: 5px solid #ff9900;
        margin-bottom: 1rem;
    }
    .error-box {
        padding: 1rem;
        background-color: #ffe6e6;
        border-left: 5px solid #cc0000;
        margin-bottom: 1rem;
    }
    .stButton button {
        background-color: #bf0000;
        color: white;
        font-weight: bold;
    }
    .stButton button:hover {
        background-color: #990000;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'api_key' not in st.session_state:
    st.session_state.api_key = os.getenv("RAKUTEN_API_KEY") # デフォルトのAPIキー

# サイドバーß
with st.sidebar:
    st.title("楽天商品情報取得ツール")
    st.markdown("---")
    
    # APIキー設定
    st.subheader("楽天APIキー設定")
    api_key = st.text_input("楽天アプリケーションID", value=st.session_state.api_key)
    if api_key:
        st.session_state.api_key = api_key
    
    st.markdown("---")
    
    # ツール選択
    st.subheader("ツール選択")
    tool = st.radio(
        "使用するツールを選択してください",
        ["キーワード検索 (競合分析)", "URL検索 (商品詳細)"]
        #["キーワード検索 (競合分析)", "URL検索 (商品詳細)", "商品コード検索"]
    )
    
    st.markdown("---")
    
    # 出力ディレクトリ
    st.subheader("出力設定")
    output_dir = st.text_input("出力ディレクトリ", value="output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    st.markdown("---")
    
    # 詳細設定
    st.subheader("詳細設定")
    headless = st.checkbox("ヘッドレスモード", value=True, help="ブラウザを表示せずに実行します")
    debug_mode = st.checkbox("デバッグモード", value=False, help="詳細なログを表示します")

# メイン画面
st.markdown("<h1 class='main-header'>楽天商品情報取得ツール</h1>", unsafe_allow_html=True)

# キーワード検索（競合分析）
if tool == "キーワード検索 (競合分析)":
    st.markdown("<h2 class='sub-header'>キーワード検索 (競合分析)</h2>", unsafe_allow_html=True)
    st.markdown("<p class='info-text'>キーワードを入力して楽天市場の商品を検索し、競合分析を行います。</p>", unsafe_allow_html=True)
    
    # 入力フォーム
    with st.form("keyword_search_form"):
        keyword = st.text_input("検索キーワード", placeholder="例: クレイクリームシャンプー")
        
        col1, col2 = st.columns(2)
        with col1:
            max_items = st.number_input("取得する商品数", min_value=1, max_value=10, value=10)
        with col2:
            sort_options = {
                "-reviewAverage": "レビュー評価の高い順",
                "+reviewAverage": "レビュー評価の低い順",
                "-reviewCount": "レビュー件数の多い順",
                "+reviewCount": "レビュー件数の少ない順",
                "-itemPrice": "価格の高い順",
                "+itemPrice": "価格の低い順",
                "standard": "標準",
                "affiliateRate": "アフィリエイト料率の高い順"
            }
            sort_order = st.selectbox("ソート順", options=list(sort_options.keys()), format_func=lambda x: sort_options[x], index=0)
        
        submit_button = st.form_submit_button("検索開始")
    
    # 検索実行
    if submit_button:
        if not keyword:
            st.markdown("<div class='error-box'>検索キーワードを入力してください。</div>", unsafe_allow_html=True)
        else:
            with st.spinner(f"「{keyword}」の商品を検索中..."):
                # 進捗バー
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # ログ表示エリア
                if debug_mode:
                    log_container = st.expander("実行ログ", expanded=True)
                    log_area = log_container.empty()
                    log_text = []
                    
                    def log_callback(message):
                        log_text.append(message)
                        log_area.text("\n".join(log_text))
                else:
                    log_callback = None
                
                try:
                    # 競合分析ツールの初期化
                    analyzer = RakutenCompetitorAnalysis(st.session_state.api_key)
                    
                    # 進捗コールバック
                    def progress_callback(current, total, message):
                        progress = min(current / total, 1.0)
                        progress_bar.progress(progress)
                        status_text.text(f"進捗: {current}/{total} - {message}")
                        if log_callback:
                            log_callback(f"[{current}/{total}] {message}")
                    
                    # 競合分析の実行
                    results = analyzer.analyze_competitors(
                        keyword, 
                        max_items=max_items, 
                        sort_order=sort_order,
                        progress_callback=progress_callback,
                        headless=headless
                    )
                    
                    # 結果の表示
                    if not results.empty:
                        # ファイル名の設定
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        filename = f"{output_dir}/rakuten_{keyword}_{timestamp}.csv"
                        
                        # 結果の保存
                        results.to_csv(filename, index=False, encoding='utf-8-sig')
                        
                        # 成功メッセージ
                        st.markdown(f"<div class='success-box'>{len(results)}件の商品情報を取得しました。</div>", unsafe_allow_html=True)
                        
                        # 結果のプレビュー
                        st.subheader("検索結果プレビュー")
                        st.dataframe(results.head(10))
                        
                        # ダウンロードボタン
                        with open(filename, "rb") as file:
                            st.download_button(
                                label="CSVファイルをダウンロード",
                                data=file,
                                file_name=os.path.basename(filename),
                                mime="text/csv"
                            )
                        
                        # 統計情報
                        st.subheader("統計情報")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("価格統計")
                            price_stats = results['itemPrice'].describe()
                            st.write(f"最低価格: {price_stats['min']:,.0f}円")
                            st.write(f"最高価格: {price_stats['max']:,.0f}円")
                            st.write(f"平均価格: {price_stats['mean']:,.0f}円")
                            st.write(f"中央価格: {price_stats['50%']:,.0f}円")
                        
                        with col2:
                            if 'reviewAverage' in results.columns:
                                st.write("レビュー評価統計")
                                rating_stats = results['reviewAverage'].describe()
                                st.write(f"平均評価: {rating_stats['mean']:.2f}点")
                                st.write(f"最高評価: {rating_stats['max']:.2f}点")
                                st.write(f"最低評価: {rating_stats['min']:.2f}点")
                    else:
                        st.markdown("<div class='warning-box'>検索結果が見つかりませんでした。</div>", unsafe_allow_html=True)
                
                except Exception as e:
                    st.markdown(f"<div class='error-box'>エラーが発生しました: {str(e)}</div>", unsafe_allow_html=True)
                    if debug_mode:
                        st.exception(e)
                
                finally:
                    # 進捗バーを完了状態に
                    progress_bar.progress(1.0)
                    status_text.text("処理が完了しました")

# URL検索（商品詳細）
elif tool == "URL検索 (商品詳細)":
    st.markdown("<h2 class='sub-header'>URL検索 (商品詳細)</h2>", unsafe_allow_html=True)
    st.markdown("<p class='info-text'>楽天商品ページのURLを入力して、商品の詳細情報を取得します。</p>", unsafe_allow_html=True)
    
    # 入力フォーム
    with st.form("url_search_form"):
        urls_text = st.text_area(
            "商品ページのURL（1行に1つ）", 
            placeholder="例:\nhttps://item.rakuten.co.jp/shop/item1/\nhttps://item.rakuten.co.jp/shop/item2/",
            height=150
        )
        
        submit_button = st.form_submit_button("情報取得開始")
    
    # 検索実行
    if submit_button:
        # URLの処理
        urls = [url.strip() for url in urls_text.split('\n') if url.strip() and url.strip().startswith('http')]
        
        if not urls:
            st.markdown("<div class='error-box'>有効なURLを入力してください。</div>", unsafe_allow_html=True)
        else:
            with st.spinner(f"{len(urls)}件のURLから情報を取得中..."):
                # 進捗バー
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # ログ表示エリア
                if debug_mode:
                    log_container = st.expander("実行ログ", expanded=True)
                    log_area = log_container.empty()
                    log_text = []
                    
                    def log_callback(message):
                        log_text.append(message)
                        log_area.text("\n".join(log_text))
                else:
                    log_callback = None
                
                try:
                    # 商品情報取得ツールの初期化
                    item_details = RakutenJSItemDetails(st.session_state.api_key)
                    
                    # 進捗コールバック
                    def progress_callback(current, total, message):
                        progress = min(current / total, 1.0)
                        progress_bar.progress(progress)
                        status_text.text(f"進捗: {current}/{total} - {message}")
                        if log_callback:
                            log_callback(f"[{current}/{total}] {message}")
                    
                    # 商品情報の取得
                    results = item_details.process_urls(
                        urls,
                        progress_callback=progress_callback,
                        headless=headless
                    )
                    
                    # 結果の表示
                    if not results.empty:
                        # ファイル名の設定
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        filename = f"{output_dir}/rakuten_url_details_{timestamp}.csv"
                        
                        # 結果の保存
                        results.to_csv(filename, index=False, encoding='utf-8-sig')
                        
                        # 成功メッセージ
                        st.markdown(f"<div class='success-box'>{len(results)}件の商品情報を取得しました。</div>", unsafe_allow_html=True)
                        
                        # 結果のプレビュー
                        st.subheader("検索結果プレビュー")
                        
                        # 表示するカラムを選択
                        display_columns = ['url', 'itemName', 'itemPrice', 'shopName']
                        if 'reviewAverage' in results.columns:
                            display_columns.append('reviewAverage')
                        if 'reviewCount' in results.columns:
                            display_columns.append('reviewCount')
                        
                        st.dataframe(results[display_columns])
                        
                        # ダウンロードボタン
                        with open(filename, "rb") as file:
                            st.download_button(
                                label="CSVファイルをダウンロード",
                                data=file,
                                file_name=os.path.basename(filename),
                                mime="text/csv"
                            )
                        
                        # 画像プレビュー
                        if 'imageUrl_1' in results.columns:
                            st.subheader("画像プレビュー")
                            image_cols = st.columns(4)
                            for i, row in results.iterrows():
                                if i < 4 and 'imageUrl_1' in row and row['imageUrl_1']:
                                    with image_cols[i % 4]:
                                        st.image(row['imageUrl_1'], caption=row.get('itemName', '商品画像'), use_column_width=True)
                    else:
                        st.markdown("<div class='warning-box'>商品情報が取得できませんでした。</div>", unsafe_allow_html=True)
                
                except Exception as e:
                    st.markdown(f"<div class='error-box'>エラーが発生しました: {str(e)}</div>", unsafe_allow_html=True)
                    if debug_mode:
                        st.exception(e)
                
                finally:
                    # 進捗バーを完了状態に
                    progress_bar.progress(1.0)
                    status_text.text("処理が完了しました")

# 商品コード検索
elif tool == "商品コード検索":
    st.markdown("<h2 class='sub-header'>商品コード検索</h2>", unsafe_allow_html=True)
    st.markdown("<p class='info-text'>楽天の商品コードを入力して、商品の詳細情報を取得します。</p>", unsafe_allow_html=True)
    
    # 入力フォーム
    with st.form("itemcode_search_form"):
        item_codes_text = st.text_area(
            "商品コード（1行に1つ）", 
            placeholder="例:\n4589596694672\n4573340595414-1\nclayshampoot2set",
            height=150
        )
        
        submit_button = st.form_submit_button("情報取得開始")
    
    # 検索実行
    if submit_button:
        # 商品コードの処理
        item_codes = [code.strip() for code in item_codes_text.split('\n') if code.strip()]
        
        if not item_codes:
            st.markdown("<div class='error-box'>商品コードを入力してください。</div>", unsafe_allow_html=True)
        else:
            with st.spinner(f"{len(item_codes)}件の商品コードから情報を取得中..."):
                # 進捗バー
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # ログ表示エリア
                if debug_mode:
                    log_container = st.expander("実行ログ", expanded=True)
                    log_area = log_container.empty()
                    log_text = []
                    
                    def log_callback(message):
                        log_text.append(message)
                        log_area.text("\n".join(log_text))
                else:
                    log_callback = None
                
                try:
                    # 商品情報取得ツールの初期化
                    item_details = RakutenItemDetails(st.session_state.api_key)
                    
                    # 進捗コールバック
                    def progress_callback(current, total, message):
                        progress = min(current / total, 1.0)
                        progress_bar.progress(progress)
                        status_text.text(f"進捗: {current}/{total} - {message}")
                        if log_callback:
                            log_callback(f"[{current}/{total}] {message}")
                    
                    # 商品情報の取得
                    results = item_details.get_items_details(
                        item_codes,
                        progress_callback=progress_callback,
                        headless=headless
                    )
                    
                    # 結果の表示
                    if not results.empty:
                        # ファイル名の設定
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        filename = f"{output_dir}/rakuten_itemcode_details_{timestamp}.csv"
                        
                        # 結果の保存
                        results.to_csv(filename, index=False, encoding='utf-8-sig')
                        
                        # 成功メッセージ
                        st.markdown(f"<div class='success-box'>{len(results)}件の商品情報を取得しました。</div>", unsafe_allow_html=True)
                        
                        # 結果のプレビュー
                        st.subheader("検索結果プレビュー")
                        
                        # 表示するカラムを選択
                        display_columns = ['itemId', 'itemName', 'itemPrice', 'shopName']
                        if 'reviewAverage' in results.columns:
                            display_columns.append('reviewAverage')
                        if 'reviewCount' in results.columns:
                            display_columns.append('reviewCount')
                        
                        st.dataframe(results[display_columns])
                        
                        # ダウンロードボタン
                        with open(filename, "rb") as file:
                            st.download_button(
                                label="CSVファイルをダウンロード",
                                data=file,
                                file_name=os.path.basename(filename),
                                mime="text/csv"
                            )
                        
                        # 画像プレビュー
                        if 'imageUrl_1' in results.columns:
                            st.subheader("画像プレビュー")
                            image_cols = st.columns(4)
                            for i, row in results.iterrows():
                                if i < 4 and 'imageUrl_1' in row and row['imageUrl_1']:
                                    with image_cols[i % 4]:
                                        st.image(row['imageUrl_1'], caption=row.get('itemName', '商品画像'), use_column_width=True)
                    else:
                        st.markdown("<div class='warning-box'>商品情報が取得できませんでした。</div>", unsafe_allow_html=True)
                
                except Exception as e:
                    st.markdown(f"<div class='error-box'>エラーが発生しました: {str(e)}</div>", unsafe_allow_html=True)
                    if debug_mode:
                        st.exception(e)
                
                finally:
                    # 進捗バーを完了状態に
                    progress_bar.progress(1.0)
                    status_text.text("処理が完了しました")

# フッター
st.markdown("---")
st.markdown("© 2023 楽天商品情報取得ツール | Powered by Rakuten API") 