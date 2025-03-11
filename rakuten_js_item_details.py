import requests
import pandas as pd
import time
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import traceback
import os

class RakutenJSItemDetails:
    def __init__(self, application_id):
        """
        楽天商品情報取得ツールの初期化
        
        Args:
            application_id (str): 楽天APIのアプリケーションID
        """
        self.application_id = application_id
        self.base_url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
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
                    "./chromedriver_li",  # linuxの場合
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
    
    def extract_js_data_from_url(self, url):
        """
        URLからJavaScriptデータを抽出
        
        Args:
            url (str): 商品ページのURL
            
        Returns:
            dict: 抽出したJSデータ
        """
        if self.driver is None:
            self.initialize_selenium()
            
        try:
            print(f"ページにアクセス中: {url}")
            self.driver.get(url)
            time.sleep(3)  # ページ読み込み待機
            
            # JavaScriptを実行してgrp15_ias_prmデータを取得
            js_data = self.driver.execute_script("""
                // grp15_ias_prmデータを探す
                for (let key in window) {
                    if (key.includes('grp15_ias_prm') && window[key]) {
                        return window[key];
                    }
                }
                
                // スクリプトタグから直接探す
                const scripts = document.getElementsByTagName('script');
                for (let i = 0; i < scripts.length; i++) {
                    const content = scripts[i].textContent || scripts[i].innerText;
                    if (content.includes('grp15_ias_prm')) {
                        const match = content.match(/var\\s+grp15_ias_prm\\s*=\\s*(\\{.*?\\});/s);
                        if (match && match[1]) {
                            try {
                                return JSON.parse(match[1]);
                            } catch (e) {
                                console.error('JSON解析エラー:', e);
                            }
                        }
                    }
                }
                
                return null;
            """)
            
            if not js_data:
                # 別の方法でスクリプトからデータを抽出
                page_source = self.driver.page_source
                pattern = r'var\s+grp15_ias_prm\s*=\s*(\{.*?\});'
                matches = re.search(pattern, page_source, re.DOTALL)
                
                if matches:
                    js_data_str = matches.group(1)
                    try:
                        # 文字列をJSONに変換
                        js_data = json.loads(js_data_str)
                    except json.JSONDecodeError:
                        print("JSONデコードエラー。正規表現で抽出したデータ:")
                        print(js_data_str[:200] + "...")
            
            if js_data:
                print("grp15_ias_prmデータを取得しました")
                return js_data
            else:
                print("grp15_ias_prmデータが見つかりませんでした")
                
                # デバッグ情報：ページのすべてのJavaScript変数を出力
                all_vars = self.driver.execute_script("""
                    const result = {};
                    for (let key in window) {
                        if (key.includes('prm') || key.includes('item') || key.includes('product')) {
                            try {
                                const value = window[key];
                                if (value && typeof value === 'object') {
                                    result[key] = value;
                                }
                            } catch (e) {}
                        }
                    }
                    return result;
                """)
                
                print("関連するJavaScript変数:")
                for key in all_vars:
                    print(f"- {key}")
                
                return None
                
        except Exception as e:
            print(f"JavaScriptデータ抽出中にエラーが発生しました: {e}")
            traceback.print_exc()
            return None
    
    def get_item_by_id(self, item_id):
        """
        商品IDに基づいて商品情報を取得
        
        Args:
            item_id (str): 楽天商品ID
            
        Returns:
            dict: API応答
        """
        params = {
            "applicationId": self.application_id,
            "itemCode": item_id,
            "hits": 1,
            "formatVersion": 2
        }
        
        try:
            response = requests.get(self.base_url, params=params)
            result = response.json()
            
            if 'Items' in result and len(result['Items']) > 0:
                return result
            else:
                # 商品コードをキーワードとして検索
                params = {
                    "applicationId": self.application_id,
                    "keyword": item_id,
                    "hits": 10,
                    "formatVersion": 2
                }
                
                response = requests.get(self.base_url, params=params)
                result = response.json()
                
                if 'Items' in result and len(result['Items']) > 0:
                    return {"Items": [result['Items'][0]]}
                else:
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
            
            # JavaScriptデータを抽出
            js_data = self.extract_js_data_from_url(item_url)
            if js_data:
                # itemidを取得
                if 'itemid' in js_data:
                    additional_info['js_itemid'] = js_data['itemid']
                    print(f"JavaScriptから取得したitemid: {js_data['itemid']}")
                
                # その他の有用な情報を取得
                for key in ['shopid', 'price', 'seller', 'category']:
                    if key in js_data:
                        additional_info[f'js_{key}'] = js_data[key]
            
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
            
            except Exception as e:
                print(f"画像取得処理中にエラーが発生しました: {e}")
            
        except Exception as e:
            print(f"追加情報の取得中にエラーが発生しました: {e}")
            traceback.print_exc()
            
        return additional_info
    
    def process_urls(self, urls, progress_callback=None, headless=True):
        """
        複数のURLから商品情報を取得
        
        Args:
            urls (list): 商品ページのURLリスト
            progress_callback (callable): 進捗を報告するコールバック関数
            headless (bool): ヘッドレスモードで実行するかどうか
            
        Returns:
            pandas.DataFrame: 商品情報
        """
        if progress_callback:
            progress_callback(0, len(urls), f"{len(urls)}件のURLから情報を取得します...")
        else:
            print(f"{len(urls)}件のURLから情報を取得します...")
        
        # 結果を格納するリスト
        results = []
        
        # Seleniumの初期化
        if self.driver is None:
            self.initialize_selenium(headless=headless)
        
        # 各URLの詳細情報を取得
        for i, url in enumerate(urls):
            if progress_callback:
                progress_callback(i+1, len(urls), f"URL {i+1}/{len(urls)} の情報を取得中: {url}")
            else:
                print(f"URL {i+1}/{len(urls)} の情報を取得中: {url}")
            
            try:
                # JavaScriptデータを抽出
                js_data = self.extract_js_data_from_url(url)
                
                if js_data and 'itemid' in js_data:
                    item_id = js_data['itemid']
                    print(f"JavaScriptから取得したitemid: {item_id}")
                    
                    # 基本情報を取得
                    item_info = {
                        'url': url,
                        'js_itemid': item_id,
                    }
                    
                    # その他のJSデータを追加
                    for key in ['shopid', 'price', 'seller', 'category']:
                        if key in js_data:
                            item_info[f'js_{key}'] = js_data[key]
                    
                    # APIから商品情報を取得
                    api_result = self.get_item_by_id(item_id)
                    
                    if 'Items' in api_result and len(api_result['Items']) > 0:
                        # 商品情報を取得
                        first_item = api_result['Items'][0]
                        if isinstance(first_item, dict) and 'Item' in first_item:
                            item = first_item['Item']
                        else:
                            item = first_item
                        
                        # APIから取得した情報を追加
                        item_info.update({
                            'itemName': item.get('itemName', '不明'),
                            'itemPrice': item.get('itemPrice', 0),
                            'itemUrl': item.get('itemUrl', ''),
                            'shopName': item.get('shopName', '不明'),
                            'itemCode': item.get('itemCode', ''),
                            'reviewCount': item.get('reviewCount', 0),
                            'reviewAverage': item.get('reviewAverage', 0),
                        })
                    
                    # 追加情報を取得
                    additional_info = self.get_additional_info(url)
                    item_info.update(additional_info)
                    
                    results.append(item_info)
                else:
                    print(f"URL {url} からJavaScriptデータを取得できませんでした")
                    
                    # JavaScriptデータがなくても追加情報は取得
                    item_info = {
                        'url': url,
                    }
                    
                    additional_info = self.get_additional_info(url)
                    item_info.update(additional_info)
                    
                    results.append(item_info)
            
            except Exception as e:
                print(f"URL {url} の処理中にエラーが発生しました: {e}")
                traceback.print_exc()
            
            # APIの制限に引っかからないよう少し待機
            time.sleep(1)
        
        # Seleniumドライバーを閉じる
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        # 結果をデータフレームに変換
        if results:
            df = pd.DataFrame(results)
            print("商品情報の取得が完了しました。")
            return df
        else:
            print("商品情報が取得できませんでした。")
            return pd.DataFrame()
    
    def save_results(self, df, filename="rakuten_js_item_details.xlsx"):
        """
        結果をファイルに保存
        
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

# 使用例
if __name__ == "__main__":
    # 楽天APIのアプリケーションIDを設定
    APPLICATION_ID = "1084639123280921528"
    
    # 取得したい商品ページのURLリスト
    URLS = [
        "https://item.rakuten.co.jp/cosme-de/j4580107383314/",
        "https://item.rakuten.co.jp/cosmeland/4589596694672/",
        "https://item.rakuten.co.jp/shop-beautiful-garden/clayshampoot2set/"
    ]
    
    # 商品情報取得ツールの初期化
    item_details = RakutenJSItemDetails(APPLICATION_ID)
    
    try:
        # 商品情報の取得
        results = item_details.process_urls(URLS)
        
        # 結果の表示
        if not results.empty:
            print("\n===== 商品情報のサンプル =====")
            # カラム名を確認
            print("利用可能なカラム:", results.columns.tolist())
            
            # 主要な情報を表示
            display_columns = ['url', 'js_itemid', 'itemName', 'itemPrice', 'shopName']
            if 'reviewAverage' in results.columns:
                display_columns.append('reviewAverage')
            if 'reviewCount' in results.columns:
                display_columns.append('reviewCount')
            
            print(results[display_columns])
            
            # 結果の保存
            item_details.save_results(results, "rakuten_js_item_details.xlsx")
        
    finally:
        # リソースの解放
        item_details.close() 