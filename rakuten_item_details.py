import requests
import pandas as pd
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re
import os

class RakutenItemDetails:
    def __init__(self, application_id):
        """
        楽天商品情報取得ツールの初期化
        
        Args:
            application_id (str): 楽天APIのアプリケーションID
        """
        self.application_id = application_id
        self.base_url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
        self.item_url = "https://app.rakuten.co.jp/services/api/IchibaItem/Get/20170706"
        self.driver = None
        
    def initialize_selenium(self, headless=True):
        """
        Seleniumドライバーの初期化
        
        Args:
            headless (bool): ヘッドレスモードで実行するかどうか
        """
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        try:
            # ChromeDriverManagerを使用して適切なバージョンを自動的に取得
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            # 最新のChromeDriverを取得（バージョン指定なし）
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"ChromeDriverManagerでのインストールに失敗: {e}")
            try:
                # 代替方法: 直接バイナリパスを指定
                from selenium.webdriver.chrome.service import Service
                
                # 各OSに応じたパスを試す
                driver_paths = [
                    "./chromedriver",  # カレントディレクトリ
                    "./chromedriver_m",  # Macの場合
                    "./chromedriver.exe",  # Windowsの場合
                    "/usr/local/bin/chromedriver",  # Linux/Macの一般的な場所
                    "/usr/bin/chromedriver"  # Linux/Macの別の場所
                ]
                
                for path in driver_paths:
                    if os.path.exists(path):
                        service = Service(path)
                        self.driver = webdriver.Chrome(service=service, options=chrome_options)
                        print(f"ローカルのChromeDriverを使用: {path}")
                        break
                else:
                    # どのパスも見つからない場合は、ChromeDriverを自動ダウンロード
                    from webdriver_manager.chrome import ChromeDriverManager
                    from webdriver_manager.core.utils import ChromeType
                    
                    # 最新の安定版を取得
                    service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as inner_e:
                print(f"代替方法でのChromeDriver初期化に失敗: {inner_e}")
                raise Exception(f"ChromeDriverの初期化に失敗しました。エラー: {e}, {inner_e}")
        
    def get_item_by_id(self, item_id):
        """
        商品IDに基づいて商品情報を取得
        
        Args:
            item_id (str): 楽天商品ID（商品コード）
            
        Returns:
            dict: API応答
        """
        # 商品コードで検索する場合は、ショップ名とアイテムコードの組み合わせが必要
        # 単純な検索APIを使用して商品コードをキーワードとして検索
        params = {
            "applicationId": self.application_id,
            "keyword": item_id,  # 商品コードをキーワードとして使用
            "hits": 10,  # 複数ヒットする可能性があるので多めに取得
            "formatVersion": 2
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            result = response.json()
            
            # 検索結果がある場合
            if 'Items' in result and len(result['Items']) > 0:
                # 完全一致する商品を探す
                for item_data in result['Items']:
                    if isinstance(item_data, dict) and 'Item' in item_data:
                        item = item_data['Item']
                    else:
                        item = item_data
                    
                    # 商品コードが一致するか確認
                    if item.get('itemCode', '').endswith(item_id) or item_id in item.get('itemCode', ''):
                        print(f"商品コード '{item_id}' に一致する商品が見つかりました: {item.get('itemName', '不明')}")
                        return {"Items": [item_data]}
                
                # 完全一致しなくても最初の結果を返す
                print(f"商品コード '{item_id}' に完全一致する商品は見つかりませんでしたが、類似の商品が見つかりました")
                return {"Items": [result['Items'][0]]}
            else:
                print(f"商品コード '{item_id}' に一致する商品が見つかりませんでした")
                return {"Items": []}
        except Exception as e:
            print(f"API呼び出し中にエラー: {e}")
            return {"Items": []}
    
    def get_additional_info(self, item_url):
        """
        Seleniumを使用して商品ページから追加情報を取得
        
        Args:
            item_url (str): 商品ページのURL
            
        Returns:
            dict: 追加情報（レビュー数、評価、Q&A数など）
        """
        if self.driver is None:
            self.initialize_selenium()
            
        self.driver.get(item_url)
        time.sleep(3)  # ページ読み込み待機時間
        
        additional_info = {}
        
        try:
            # ページのタイトルを取得（デバッグ用）
            print(f"ページタイトル: {self.driver.title}")
            
            # レビュー情報の取得（複数のセレクタを試す）
            review_selectors = [
                "span[itemprop='aggregateRating']",
                "span.revRating",
                "div.revRating",
                "div.item-review-area"
            ]
            
            review_element = None
            for selector in review_selectors:
                try:
                    review_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    if review_element:
                        print(f"レビュー要素が見つかりました: {selector}")
                        break
                except:
                    continue
            
            if review_element:
                review_text = review_element.text
                print(f"レビューテキスト: {review_text}")
                
                # 評価点数を抽出
                rating_match = re.search(r'([0-9.]+)点', review_text)
                if rating_match:
                    additional_info['rating'] = float(rating_match.group(1))
                
                # レビュー件数を抽出
                review_count_match = re.search(r'([0-9,]+)件', review_text)
                if review_count_match:
                    additional_info['reviewCount'] = int(review_count_match.group(1).replace(',', ''))
            else:
                print("レビュー要素が見つかりませんでした")
                
            # 商品説明の取得
            description_selectors = [
                "div.item-description",
                "div.itemDescription",
                "div#item-description",
                "div.item-exp"
            ]
            
            for selector in description_selectors:
                try:
                    description = self.driver.find_element(By.CSS_SELECTOR, selector).text
                    if description:
                        additional_info['description'] = description
                        break
                except:
                    continue
            
            if 'description' not in additional_info:
                additional_info['description'] = "説明が見つかりません"
                
            # 指定されたクラス名の画像を取得
            try:
                print("指定されたクラス名 'image--3z5RH' の画像を取得中...")
                
                # ページが完全に読み込まれるのを待つ
                time.sleep(2)
                
                # JavaScriptを実行して遅延読み込み画像を表示させる
                self.driver.execute_script("""
                    // 画面をスクロールして遅延読み込み画像を表示
                    window.scrollTo(0, document.body.scrollHeight / 2);
                    setTimeout(() => { window.scrollTo(0, 0); }, 500);
                """)
                time.sleep(2)
                
                # 指定されたクラスの画像要素を取得
                image_elements = self.driver.find_elements(By.CSS_SELECTOR, ".image--3z5RH")
                
                if image_elements:
                    print(f"'image--3z5RH' クラスの画像要素が {len(image_elements)} 個見つかりました")
                    
                    # 画像URLを格納するリスト
                    image_urls = []
                    
                    # 各画像要素からURLを取得
                    for img in image_elements:
                        try:
                            # src属性を確認
                            src = img.get_attribute('src')
                            if src and src.startswith('http'):
                                image_urls.append(src)
                            else:
                                # data-src属性を確認
                                data_src = img.get_attribute('data-src')
                                if data_src and data_src.startswith('http'):
                                    image_urls.append(data_src)
                        except Exception as e:
                            print(f"画像URL取得中にエラー: {e}")
                    
                    # 重複を削除
                    image_urls = list(dict.fromkeys(image_urls))
                    
                    # 高解像度版に変換
                    image_urls = [re.sub(r'_ex=\d+x\d+', '_ex=500x500', url) if '_ex=' in url else url for url in image_urls]
                    
                    print(f"取得した画像URL数: {len(image_urls)}")
                    
                    # 最大20枚まで保存
                    for i, img_url in enumerate(image_urls[:20]):
                        additional_info[f'imageUrl_{i+1}'] = img_url
                    
                    # 画像の総数も保存
                    additional_info['imageCount'] = len(image_urls[:20])
                    
                    # すべての画像URLをパイプ区切りで保存
                    additional_info['allImageUrls'] = '|'.join(image_urls[:20])
                else:
                    print("'image--3z5RH' クラスの画像要素が見つかりませんでした")
                    
                    # 代替方法：他の一般的な画像セレクタを試す
                    alternative_selectors = [
                        "div.image-gallery img",
                        "div.item-image-container img",
                        "div.item-image img",
                        "div.item-gallery img",
                        "div.item-photo img"
                    ]
                    
                    for selector in alternative_selectors:
                        try:
                            alt_images = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if alt_images:
                                print(f"代替セレクタ '{selector}' で {len(alt_images)} 個の画像を発見")
                                
                                # 画像URLを格納するリスト
                                alt_image_urls = []
                                
                                # 各画像要素からURLを取得
                                for img in alt_images:
                                    src = img.get_attribute('src') or img.get_attribute('data-src')
                                    if src and src.startswith('http'):
                                        alt_image_urls.append(src)
                                
                                if alt_image_urls:
                                    # 重複を削除
                                    alt_image_urls = list(dict.fromkeys(alt_image_urls))
                                    
                                    # 高解像度版に変換
                                    alt_image_urls = [re.sub(r'_ex=\d+x\d+', '_ex=500x500', url) if '_ex=' in url else url for url in alt_image_urls]
                                    
                                    # 最大20枚まで保存
                                    for i, img_url in enumerate(alt_image_urls[:20]):
                                        additional_info[f'imageUrl_{i+1}'] = img_url
                                    
                                    # 画像の総数も保存
                                    additional_info['imageCount'] = len(alt_image_urls[:20])
                                    
                                    # すべての画像URLをパイプ区切りで保存
                                    additional_info['allImageUrls'] = '|'.join(alt_image_urls[:20])
                                    
                                    break
                        except Exception as e:
                            print(f"代替画像取得中にエラー: {e}")
            
            except Exception as e:
                print(f"画像取得処理中にエラーが発生しました: {e}")
            
        except Exception as e:
            print(f"追加情報の取得中にエラーが発生しました: {e}")
            
        return additional_info
    
    def get_items_details(self, item_ids, progress_callback=None, headless=True):
        """
        複数の商品IDから詳細情報を取得
        
        Args:
            item_ids (list): 楽天商品IDのリスト
            progress_callback (callable): 進捗を報告するコールバック関数
            headless (bool): ヘッドレスモードで実行するかどうか
            
        Returns:
            pandas.DataFrame: 商品詳細情報
        """
        if progress_callback:
            progress_callback(0, len(item_ids), f"{len(item_ids)}件の商品IDから情報を取得します...")
        else:
            print(f"{len(item_ids)}件の商品IDから情報を取得します...")
        
        # 結果を格納するリスト
        results = []
        
        # Seleniumの初期化
        if self.driver is None:
            self.initialize_selenium(headless=headless)
        
        # 各商品IDの詳細情報を取得
        for i, item_id in enumerate(item_ids):
            if progress_callback:
                progress_callback(i+1, len(item_ids), f"商品 {i+1}/{len(item_ids)} の情報を取得中: {item_id}")
            else:
                print(f"商品 {i+1}/{len(item_ids)} の情報を取得中: {item_id}")
            
            # APIから商品情報を取得
            api_result = self.get_item_by_id(item_id)
            
            # デバッグ用にAPIレスポンスの構造を確認（最初の商品のみ）
            if i == 0:
                print("APIレスポンス構造:", json.dumps(api_result, indent=2, ensure_ascii=False)[:500] + "...")
            
            # APIからの応答を確認
            if 'Items' not in api_result or len(api_result['Items']) == 0:
                print(f"商品ID {item_id} の情報が見つかりませんでした。")
                continue
            
            # 商品情報を取得
            item_data = api_result['Items'][0]
            
            # formatVersion=2の場合、直接itemデータが含まれている可能性があります
            if isinstance(item_data, dict) and 'Item' in item_data:
                item = item_data['Item']
            else:
                # 直接itemデータとして扱う
                item = item_data
            
            # APIから取得した基本情報
            item_info = {
                'itemId': item_id,
                'itemName': item.get('itemName', '不明'),
                'itemPrice': item.get('itemPrice', 0),
                'itemUrl': item.get('itemUrl', ''),
                'shopName': item.get('shopName', '不明'),
                'itemCode': item.get('itemCode', ''),
                'imageUrl': None,  # デフォルト値をNoneに設定
                'availability': item.get('availability', ''),
                'taxFlag': item.get('taxFlag', 0),
                'postageFlag': item.get('postageFlag', 0),
                'creditCardFlag': item.get('creditCardFlag', 0),
                'reviewCount': item.get('reviewCount', 0),
                'reviewAverage': item.get('reviewAverage', 0),
                'pointRate': item.get('pointRate', 0),
                'pointRateStartTime': item.get('pointRateStartTime', ''),
                'pointRateEndTime': item.get('pointRateEndTime', ''),
                'shopOfTheYearFlag': item.get('shopOfTheYearFlag', 0),
                'shipOverseasFlag': item.get('shipOverseasFlag', 0),
                'shipOverseasArea': item.get('shipOverseasArea', ''),
                'asurakuFlag': item.get('asurakuFlag', 0),
                'asurakuClosingTime': item.get('asurakuClosingTime', ''),
                'asurakuArea': item.get('asurakuArea', ''),
                'affiliateRate': item.get('affiliateRate', 0),
                'startTime': item.get('startTime', ''),
                'endTime': item.get('endTime', ''),
                'giftFlag': item.get('giftFlag', 0),
                'tagIds': ','.join(map(str, item.get('tagIds', []))),
            }
            
            # 画像URLの取得を安全に行う
            try:
                # 単一の画像URL（メイン画像）
                medium_image_urls = item.get('mediumImageUrls')
                if medium_image_urls:
                    if isinstance(medium_image_urls, list) and len(medium_image_urls) > 0:
                        if isinstance(medium_image_urls[0], dict) and 'imageUrl' in medium_image_urls[0]:
                            item_info['imageUrl'] = medium_image_urls[0]['imageUrl']
                        elif isinstance(medium_image_urls[0], str):
                            item_info['imageUrl'] = medium_image_urls[0]
                    elif isinstance(medium_image_urls, str):
                        item_info['imageUrl'] = medium_image_urls
            except Exception as e:
                print(f"画像URL取得中にエラーが発生しました: {e}")
            
            # 商品URLが存在する場合のみSeleniumで追加情報を取得
            if item_info['itemUrl']:
                additional_info = self.get_additional_info(item_info['itemUrl'])
                # 基本情報と追加情報を結合
                item_info.update(additional_info)
            
            results.append(item_info)
            
            # APIの制限に引っかからないよう少し待機
            time.sleep(1)
        
        # Seleniumドライバーを閉じる
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        # 結果をデータフレームに変換
        df = pd.DataFrame(results)
        
        print("商品情報の取得が完了しました。")
        return df
    
    def save_results(self, df, filename="rakuten_item_details.xlsx"):
        """
        分析結果をファイルに保存
        
        Args:
            df (pandas.DataFrame): 保存するデータフレーム
            filename (str): 保存するファイル名
        """
        try:
            # Excelファイルとして保存を試みる
            df.to_excel(filename, index=False)
            print(f"商品情報を {filename} に保存しました。")
        except ModuleNotFoundError:
            # openpyxlがない場合はCSVで保存
            csv_filename = filename.replace('.xlsx', '.csv')
            df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"openpyxlモジュールがインストールされていないため、{csv_filename} としてCSV形式で保存しました。")
            print("Excelで保存するには: pip install openpyxl を実行してください。")
        
    def close(self):
        """
        リソースを解放
        """
        if self.driver:
            self.driver.quit()
            self.driver = None

    def search_items_by_keyword(self, keyword, hits=5):
        """
        キーワードで商品を検索
        
        Args:
            keyword (str): 検索キーワード
            hits (int): 取得する商品数
            
        Returns:
            dict: API応答
        """
        params = {
            "applicationId": self.application_id,
            "keyword": keyword,
            "hits": hits,
            "formatVersion": 2
        }
        
        response = requests.get(self.base_url, params=params)
        return response.json()

# 使用例
if __name__ == "__main__":
    # 楽天APIのアプリケーションIDを設定
    APPLICATION_ID = "1084639123280921528"
    
    # 検索方法を選択（'keyword' または 'itemcode'）
    SEARCH_METHOD = 'itemcode'  # 'keyword' または 'itemcode'
    
    if SEARCH_METHOD == 'keyword':
        # キーワードリスト
        SEARCH_TERMS = [
            "クレイクリームシャンプー",
            "モイストダイアン",
            "ミルボン"
        ]
    else:
        # 商品コードリスト
        SEARCH_TERMS = [
            "4589596694672",
            "4573340595414-1",
            "clayshampoot2set"
        ]
    
    # 商品情報取得ツールの初期化
    item_details = RakutenItemDetails(APPLICATION_ID)
    
    try:
        # 結果を格納するリスト
        all_results = []
        
        for term in SEARCH_TERMS:
            if SEARCH_METHOD == 'keyword':
                print(f"キーワード '{term}' で商品を検索中...")
                search_results = item_details.search_items_by_keyword(term)
            else:
                print(f"商品コード '{term}' で商品を検索中...")
                search_results = item_details.get_item_by_id(term)
            
            if 'Items' in search_results and len(search_results['Items']) > 0:
                # 商品情報を取得
                first_item = search_results['Items'][0]
                if isinstance(first_item, dict) and 'Item' in first_item:
                    item = first_item['Item']
                else:
                    item = first_item
                
                print(f"商品が見つかりました: {item.get('itemName', '不明')}")
                
                # 商品URLから詳細情報を取得
                item_url = item.get('itemUrl', '')
                if item_url:
                    print(f"商品ページから詳細情報を取得中: {item_url}")
                    additional_info = item_details.get_additional_info(item_url)
                    
                    # 基本情報と追加情報を結合
                    item_info = {
                        'searchTerm': term,
                        'itemName': item.get('itemName', '不明'),
                        'itemPrice': item.get('itemPrice', 0),
                        'itemUrl': item_url,
                        'shopName': item.get('shopName', '不明'),
                        'itemCode': item.get('itemCode', ''),
                        'reviewCount': item.get('reviewCount', 0),
                        'reviewAverage': item.get('reviewAverage', 0),
                    }
                    
                    item_info.update(additional_info)
                    all_results.append(item_info)
            else:
                print(f"検索語 '{term}' に一致する商品が見つかりませんでした。")
        
        # 結果をデータフレームに変換
        if all_results:
            results_df = pd.DataFrame(all_results)
            
            # 結果の表示
            print("\n===== 商品情報のサンプル =====")
            print("利用可能なカラム:", results_df.columns.tolist())
            
            # 主要な情報を表示
            display_columns = ['searchTerm', 'itemName', 'itemPrice', 'shopName', 'reviewAverage']
            if 'reviewCount' in results_df.columns:
                display_columns.append('reviewCount')
            
            print(results_df[display_columns])
            
            # 結果の保存
            filename = "rakuten_item_search_results.xlsx"
            item_details.save_results(results_df, filename)
            print(f"結果を {filename} に保存しました")
        else:
            print("商品情報が取得できませんでした。")
    
    finally:
        # リソースの解放
        item_details.close() 