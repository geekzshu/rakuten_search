import streamlit as st
import pandas as pd
import time
import os
from dotenv import load_dotenv
from rakuten_competitor_analysis import RakutenCompetitorAnalysis
from rakuten_item_details import RakutenItemDetails
from rakuten_js_item_details import RakutenJSItemDetails
import base64
from datetime import datetime

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
    #api_key = st.text_input("楽天アプリケーションID", value="1000000000000000")
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

# サイドバーにメニューを追加
st.sidebar.title("メニュー")
page = st.sidebar.radio(
    "ページを選択してください",
    ["競合分析", "CSVファイル一覧"]
)

if page == "競合分析":
    # 既存の競合分析コード
    st.title("楽天市場 競合商品分析ツール")
    
    # ツール選択に基づいて処理
    if tool == "キーワード検索 (競合分析)":
        st.markdown("<h2 class='sub-header'>キーワード検索 (競合分析)</h2>", unsafe_allow_html=True)
        st.markdown("<p class='info-text'>キーワードを入力して楽天市場の商品を検索し、競合分析を行います。</p>", unsafe_allow_html=True)
        
        # 入力フォーム
        with st.form("keyword_search_form"):
            keyword = st.text_input("検索キーワード", placeholder="例: クレイクリームシャンプー")
            
            col1, col2 = st.columns(2)
            with col1:
                max_items = st.number_input("取得する商品数", min_value=1, max_value=5, value=1)
            with col2:
                sort_options = {
                    "-reviewCount": "レビュー件数の多い順",
                    "+reviewCount": "レビュー件数の少ない順",
                    "-reviewAverage": "レビュー評価の高い順",
                    "+reviewAverage": "レビュー評価の低い順",
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

                            # レビュー情報の表示とCSVダウンロード
                            if any(col.startswith('review_1_') for col in results.columns):
                                st.subheader("レビュー情報")
                                
                                # レビュー情報をCSVに保存
                                reviews_file = analyzer.save_reviews_to_csv(results, keyword, output_dir)
                                
                                # レビュー情報の表示
                                review_tabs = st.tabs(["レビューサンプル", "レビュー統計", "全レビュー"])
                                
                                with review_tabs[0]:
                                    # レビューサンプル（最初の3商品の最初の3レビュー）
                                    for i, row in results.iterrows():
                                        if i < 3:  # 最初の3商品のみ表示
                                            st.markdown(f"**{row['itemName']}**")
                                            for j in range(1, 4):  # 最初の3レビュー
                                                review_comment_col = f'review_{j}_comment'
                                                if review_comment_col in row and pd.notna(row[review_comment_col]) and row[review_comment_col]:
                                                    rating_col = f'review_{j}_rating'
                                                    title_col = f'review_{j}_title'
                                                    date_col = f'review_{j}_date'
                                                    
                                                    rating = row[rating_col] if rating_col in row and pd.notna(row[rating_col]) else "不明"
                                                    title = row[title_col] if title_col in row and pd.notna(row[title_col]) else "タイトルなし"
                                                    date = row[date_col] if date_col in row and pd.notna(row[date_col]) else ""
                                                    
                                                    st.markdown(f"⭐ {rating} - **{title}**")
                                                    st.markdown(f"_{row[review_comment_col]}_")
                                                    if date:
                                                        st.markdown(f"({date})")
                                                    st.markdown("---")
                                
                                with review_tabs[1]:
                                    # レビュー統計
                                    st.markdown("### レビュー評価の分布")
                                    
                                    # レビュー評価の分布を計算
                                    rating_columns = [col for col in results.columns if col.startswith('review_') and col.endswith('_rating')]
                                    if rating_columns:
                                        all_ratings = []
                                        for col in rating_columns:
                                            ratings = results[col].dropna().tolist()
                                            all_ratings.extend(ratings)
                                        
                                        if all_ratings:
                                            # ヒストグラムを表示
                                            import matplotlib.pyplot as plt
                                            import numpy as np
                                            
                                            fig, ax = plt.subplots(figsize=(10, 6))
                                            bins = np.arange(0.5, 6.0, 0.5)  # 0.5刻みでビンを作成
                                            ax.hist(all_ratings, bins=bins, alpha=0.7, color='#bf0000')
                                            ax.set_xlabel('レビュー評価')
                                            ax.set_ylabel('レビュー数')
                                            ax.set_title(f'{keyword} のレビュー評価分布')
                                            ax.grid(True, linestyle='--', alpha=0.7)
                                            st.pyplot(fig)
                                            
                                            # 基本統計量
                                            import numpy as np
                                            st.markdown("### レビュー評価の統計")
                                            st.write(f"平均評価: {np.mean(all_ratings):.2f}点")
                                            st.write(f"最高評価: {np.max(all_ratings):.2f}点")
                                            st.write(f"最低評価: {np.min(all_ratings):.2f}点")
                                            st.write(f"中央値: {np.median(all_ratings):.2f}点")
                                            st.write(f"標準偏差: {np.std(all_ratings):.2f}")
                                            st.write(f"レビュー総数: {len(all_ratings)}件")
                                        else:
                                            st.write("レビュー評価データがありません。")
                                    else:
                                        st.write("レビュー評価データがありません。")
                                
                                with review_tabs[2]:
                                    # 全レビューをテーブルとして表示
                                    st.markdown("### 全レビュー一覧")
                                    
                                    # レビューデータを収集
                                    review_data = []
                                    for i, row in results.iterrows():
                                        item_name = row.get('itemName', '不明')
                                        shop_name = row.get('shopName', '不明')
                                        
                                        for j in range(1, 6):  # 最大5件のレビュー
                                            rating_col = f'review_{j}_rating'
                                            title_col = f'review_{j}_title'
                                            comment_col = f'review_{j}_comment'
                                            date_col = f'review_{j}_date'
                                            
                                            if all(col in row for col in [rating_col, title_col, comment_col, date_col]):
                                                if pd.notna(row[comment_col]) and row[comment_col]:
                                                    review_data.append({
                                                        '商品名': item_name,
                                                        'ショップ名': shop_name,
                                                        '評価': row.get(rating_col),
                                                        'タイトル': row.get(title_col),
                                                        'コメント': row.get(comment_col),
                                                        '日付': row.get(date_col)
                                                    })
                                    
                                    if review_data:
                                        reviews_df = pd.DataFrame(review_data)
                                        st.dataframe(reviews_df, use_container_width=True)
                                    else:
                                        st.write("レビューデータがありません。")
                                    
                                    # レビューCSVのダウンロードボタン
                                    if reviews_file and os.path.exists(reviews_file):
                                        with open(reviews_file, "rb") as file:
                                            st.download_button(
                                                label="レビュー情報をCSVでダウンロード",
                                                data=file,
                                                file_name=os.path.basename(reviews_file),
                                                mime="text/csv"
                                            )
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

    elif tool == "URL検索 (商品詳細)":
        st.markdown("<h2 class='sub-header'>URL検索 (商品詳細)</h2>", unsafe_allow_html=True)
        st.markdown("<p class='info-text'>楽天市場の商品URLを入力して詳細情報を取得します。</p>", unsafe_allow_html=True)
        
        # Streamlit Cloud環境かどうかを確認
        is_streamlit_cloud = os.environ.get('STREAMLIT_SHARING', '') or os.environ.get('STREAMLIT_CLOUD', '')
        
        # 入力フォーム
        with st.form("url_search_form"):
            item_url = st.text_input("商品URL", placeholder="https://item.rakuten.co.jp/...")
            
            # Seleniumの使用有無を選択（Streamlit Cloudでは無効化）
            if is_streamlit_cloud:
                st.warning("Streamlit Cloud環境ではSeleniumが使用できないため、基本情報のみ取得します。")
                use_selenium = False
            else:
                use_selenium = st.checkbox("Seleniumを使用する（詳細情報取得）", value=True, help="オフにすると基本情報のみ取得します")
            
            submit_button = st.form_submit_button("検索開始")
        
        # 検索実行
        if submit_button:
            if not item_url:
                st.markdown("<div class='error-box'>商品URLを入力してください。</div>", unsafe_allow_html=True)
            else:
                with st.spinner(f"商品情報を取得中..."):
                    # 進捗バー
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # ログ表示エリア
                    if debug_mode:
                        log_container = st.expander("実行ログ", expanded=True)
                        log_area = log_container.empty()
                    
                    try:
                        # 商品コードを抽出
                        import re
                        item_code_match = re.search(r'/([^/]+)/([^/]+)$', item_url)
                        
                        if not item_code_match:
                            st.error("URLから商品コードを抽出できませんでした。")
                            progress_bar.progress(1.0)
                            status_text.text("処理が完了しました")
                        else:
                            # 商品コードが抽出できた場合の処理
                            shop_code = item_code_match.group(1)
                            item_code = item_code_match.group(2)
                            full_item_code = f"{shop_code}:{item_code}"
                            
                            # APIを使用した基本情報取得
                            item_details = RakutenItemDetails(st.session_state.api_key)
                            
                            # 進捗状況の更新
                            progress_bar.progress(0.3)
                            status_text.text("商品情報をAPIから取得中...")
                            
                            # 商品情報の取得
                            item_data = item_details.get_item_by_code(full_item_code)
                            
                            # 進捗状況の更新
                            progress_bar.progress(0.8)
                            status_text.text("商品情報を処理中...")
                            
                            # 結果の表示
                            if item_data:
                                # ファイル名の設定
                                timestamp = time.strftime("%Y%m%d_%H%M%S")
                                filename = f"{output_dir}/rakuten_url_details_{timestamp}.csv"
                                
                                # 結果の保存
                                pd.DataFrame([item_data]).to_csv(filename, index=False, encoding='utf-8-sig')
                                
                                # 成功メッセージ
                                st.markdown(f"<div class='success-box'>商品情報を取得しました。</div>", unsafe_allow_html=True)
                                
                                # 結果のプレビュー
                                st.subheader("取得した商品情報")
                                st.dataframe(pd.DataFrame([item_data]))
                                
                                # ダウンロードボタン
                                with open(filename, "rb") as f:
                                    st.download_button(
                                        label="CSVファイルをダウンロード",
                                        data=f,
                                        file_name=f"rakuten_item_{shop_code}_{item_code}.csv",
                                        mime="text/csv"
                                    )
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
                                st.subheader("商品画像サンプル")
                                image_cols = st.columns(4)
                                for i, row in results.iterrows():
                                    if i < 4 and 'imageUrl_1' in row and row['imageUrl_1']:
                                        with image_cols[i % 4]:
                                            st.image(row['imageUrl_1'], caption=row.get('itemName', '商品画像'), use_container_width=True)

                            # レビューサンプル
                            if any(col.startswith('review_1_') for col in results.columns):
                                st.subheader("レビューサンプル")
                                for i, row in results.iterrows():
                                    if i < 3:  # 最初の3商品のみ表示
                                        st.markdown(f"**{row['itemName']}**")
                                        for j in range(1, 6):  # 最大5件のレビュー
                                            review_comment_col = f'review_{j}_comment'
                                            if review_comment_col in row and pd.notna(row[review_comment_col]) and row[review_comment_col]:
                                                rating_col = f'review_{j}_rating'
                                                title_col = f'review_{j}_title'
                                                date_col = f'review_{j}_date'
                                                
                                                rating = row[rating_col] if rating_col in row and pd.notna(row[rating_col]) else "不明"
                                                title = row[title_col] if title_col in row and pd.notna(row[title_col]) else "タイトルなし"
                                                date = row[date_col] if date_col in row and pd.notna(row[date_col]) else ""
                                                
                                                st.markdown(f"⭐ {rating} - **{title}**")
                                                st.markdown(f"_{row[review_comment_col]}_")
                                                if date:
                                                    st.markdown(f"({date})")
                                                st.markdown("---")
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

elif page == "CSVファイル一覧":
    st.title("保存済みCSVファイル一覧")
    
    # outputフォルダ内のCSVファイルを取得
    output_dir = "output"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    csv_files = [f for f in os.listdir(output_dir) if f.endswith('.csv')]
    
    if not csv_files:
        st.info("保存されたCSVファイルがありません。競合分析を実行してデータを生成してください。")
    else:
        # ファイルを日付順に並べ替え（新しい順）
        csv_files.sort(key=lambda x: os.path.getmtime(os.path.join(output_dir, x)), reverse=True)
        
        # ファイル一覧をテーブルとして表示
        file_data = []
        for file in csv_files:
            file_path = os.path.join(output_dir, file)
            file_size = os.path.getsize(file_path) / 1024  # KBに変換
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # ファイルの内容をプレビュー
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig', nrows=1)
                row_count = len(pd.read_csv(file_path, encoding='utf-8-sig'))
                columns = ", ".join(df.columns.tolist())
            except Exception as e:
                row_count = "エラー"
                columns = f"読み込みエラー: {str(e)}"
            
            file_data.append({
                "ファイル名": file,
                "サイズ (KB)": f"{file_size:.1f}",
                "行数": row_count,
                "更新日時": mod_time.strftime("%Y-%m-%d %H:%M:%S"),
                "列": columns
            })
        
        # データフレームとして表示
        st.dataframe(pd.DataFrame(file_data))
        
        # 複数ファイル選択
        st.subheader("ファイルの選択とダウンロード")
        
        # チェックボックスでファイルを選択
        selected_files = {}
        cols = st.columns(3)
        for i, file in enumerate(csv_files):
            col_idx = i % 3
            with cols[col_idx]:
                selected_files[file] = st.checkbox(file, key=f"file_{i}")
        
        # 選択されたファイルを取得
        files_to_download = [file for file, selected in selected_files.items() if selected]
        
        if files_to_download:
            st.success(f"{len(files_to_download)}個のファイルが選択されました")
            
            # 選択したファイルをZIPにまとめてダウンロード
            if len(files_to_download) > 1:
                import zipfile
                import io
                
                # ZIPファイルを作成
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for file in files_to_download:
                        file_path = os.path.join(output_dir, file)
                        zip_file.write(file_path, arcname=file)
                
                # ZIPファイルをダウンロード
                zip_buffer.seek(0)
                st.download_button(
                    label=f"選択した{len(files_to_download)}個のファイルをZIPでダウンロード",
                    data=zip_buffer,
                    file_name="rakuten_csv_files.zip",
                    mime="application/zip"
                )
            
            # 個別ファイルのダウンロードボタン
            st.subheader("個別ファイルのダウンロード")
            for file in files_to_download:
                file_path = os.path.join(output_dir, file)
                with open(file_path, "rb") as f:
                    st.download_button(
                        label=f"{file} をダウンロード",
                        data=f,
                        file_name=file,
                        mime="text/csv",
                        key=f"download_{file}"
                    )
        
        # 選択したファイルのプレビュー
        if len(files_to_download) == 1:
            selected_file = files_to_download[0]
            file_path = os.path.join(output_dir, selected_file)
            
            # ファイルの内容をプレビュー
            try:
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                st.subheader(f"ファイルプレビュー: {selected_file}")
                st.dataframe(df.head(10))  # 最初の10行を表示
                
                # ファイル削除オプション
                if st.button(f"ファイル「{selected_file}」を削除"):
                    try:
                        os.remove(file_path)
                        st.success(f"ファイル「{selected_file}」を削除しました。")
                        st.experimental_rerun()  # ページを再読み込み
                    except Exception as e:
                        st.error(f"ファイル削除中にエラーが発生しました: {e}")
                
            except Exception as e:
                st.error(f"ファイル読み込み中にエラーが発生しました: {e}")
        
        # 複数ファイル削除オプション
        if len(files_to_download) > 1:
            if st.button(f"選択した{len(files_to_download)}個のファイルを削除"):
                try:
                    for file in files_to_download:
                        file_path = os.path.join(output_dir, file)
                        os.remove(file_path)
                    st.success(f"選択した{len(files_to_download)}個のファイルを削除しました。")
                    st.experimental_rerun()  # ページを再読み込み
                except Exception as e:
                    st.error(f"ファイル削除中にエラーが発生しました: {e}")

    # フッター
    st.markdown("---")
    st.markdown("© 2023 楽天商品情報取得ツール | Powered by Rakuten API") 