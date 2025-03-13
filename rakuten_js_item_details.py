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
from rakuten_init import RakutenInit
import traceback
import os
import platform

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
        
    
    def extract_js_data_from_url(self, url):
        """
        URLからJavaScriptデータを抽出
        
        Args:
            url (str): 商品ページのURL
            
        Returns:
            dict: 抽出したJSデータ
        """
        if self.driver is None:
            rakuten_init = RakutenInit(self.application_id)
            rakuten_init.initialize_selenium()
            self.driver = rakuten_init.driver
            
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
            rakuten_init = RakutenInit(self.application_id)
            rakuten_init.initialize_selenium()
            self.driver = rakuten_init.driver
            
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
    
    def process_urls(self, urls, progress_callback=None):
        """
        複数のURLを処理
        
        Args:
            urls (list): 処理するURLのリスト
            progress_callback (function, optional): 進捗コールバック関数
            
        Returns:
            pandas.DataFrame: 処理結果
        """
        results = []
        
        for i, url in enumerate(urls):
            if progress_callback:
                progress_callback(i, len(urls), f"URL {i+1}/{len(urls)} を処理中...")
            
            print(f"\n===== URL {i+1}/{len(urls)} を処理中: {url} =====")
            
            # 直接スクレイピングで情報を取得
            item_info = self.get_item_by_url(url)
            
            if item_info and "error" not in item_info:
                # 成功した場合は結果に追加
                item_info["url"] = url
                results.append(item_info)
                print(f"商品情報を取得しました: {item_info.get('itemName', '不明')}")
            else:
                # エラーの場合は代替方法を試す
                print("直接スクレイピングに失敗。代替方法を試します...")
                
                # 代替方法1: JavaScriptデータから取得
                js_data = self.extract_js_data_from_url(url)
                if js_data:
                    item_details = self.extract_item_details_from_js(js_data, url)
                    if item_details and "error" not in item_details:
                        item_details["url"] = url
                        results.append(item_details)
                        print(f"JavaScriptデータから商品情報を取得: {item_details.get('itemName', '不明')}")
                        continue
                
                # 代替方法2: HTMLから直接抽出
                html_info = self.extract_info_from_html(url)
                if html_info and "error" not in html_info:
                    html_info["url"] = url
                    results.append(html_info)
                    print(f"HTMLから商品情報を取得: {html_info.get('itemName', '不明')}")
                    continue
                
                # すべての方法が失敗した場合
                print(f"URL {url} からの商品情報取得に失敗しました")
                results.append({
                    "url": url,
                    "itemName": "取得失敗",
                    "itemPrice": 0,
                    "shopName": "不明",
                    "error": "商品情報を取得できませんでした"
                })
        
        if progress_callback:
            progress_callback(len(urls), len(urls), "処理完了")
        
        # 結果をデータフレームに変換
        if results:
            df = pd.DataFrame(results)
            return df
        else:
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

    def extract_item_code_from_url(self, url):
        """
        URLから商品コードを抽出
        
        Args:
            url (str): 商品ページのURL
            
        Returns:
            str: 商品コード
        """
        if not url:
            return None
        
        # 複数のパターンを試す
        patterns = [
            # 標準的な楽天市場のURL形式
            r'item/([a-zA-Z0-9_\-]+)/',
            r'items/([a-zA-Z0-9_\-]+)/',
            # 別の形式
            r'item-([a-zA-Z0-9_\-]+)\.html',
            r'item_([a-zA-Z0-9_\-]+)\.html',
            # クエリパラメータ形式
            r'item.php\?itemcode=([a-zA-Z0-9_\-]+)',
            r'item\.php\?item_id=([a-zA-Z0-9_\-]+)',
            # 最後のフォールバック - スラッシュで区切られた最後の部分
            r'/([a-zA-Z0-9_\-]+)(?:\.html)?$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                item_code = match.group(1)
                print(f"URLから商品コードを抽出: {item_code}")
                return item_code
        
        # URLを出力してデバッグ
        print(f"URLから商品コードを抽出できませんでした: {url}")
        
        # 最終手段: URLの最後の部分を取得
        parts = url.rstrip('/').split('/')
        if parts:
            last_part = parts[-1]
            if '.' in last_part:
                last_part = last_part.split('.')[0]
            if last_part and not last_part.startswith('http'):
                print(f"URLの最後の部分を商品コードとして使用: {last_part}")
                return last_part
        
        return None

    def extract_item_details_from_js(self, js_data, url):
        """
        JavaScriptデータから商品詳細を抽出
        
        Args:
            js_data (dict): JavaScriptデータ
            url (str): 商品ページのURL
            
        Returns:
            dict: 商品詳細情報
        """
        if not js_data:
            return {"error": "JavaScriptデータがありません"}
        
        # デバッグ情報
        print("JavaScriptデータのキー:", list(js_data.keys()) if isinstance(js_data, dict) else "データ型が辞書ではありません")
        
        item_details = {
            "itemUrl": url,
            "source": "js_data"
        }
        
        # 商品名
        if 'name' in js_data:
            item_details['itemName'] = js_data['name']
        elif 'item_name' in js_data:
            item_details['itemName'] = js_data['item_name']
        elif 'title' in js_data:
            item_details['itemName'] = js_data['title']
        
        # 価格
        if 'price' in js_data:
            try:
                item_details['itemPrice'] = int(js_data['price'])
            except (ValueError, TypeError):
                # 数値以外の文字を削除して整数に変換
                price_str = re.sub(r'[^\d]', '', str(js_data['price']))
                if price_str:
                    item_details['itemPrice'] = int(price_str)
        
        # 商品コード
        if 'item_id' in js_data:
            item_details['itemCode'] = js_data['item_id']
        elif 'itemCode' in js_data:
            item_details['itemCode'] = js_data['itemCode']
        elif 'sku' in js_data:
            item_details['itemCode'] = js_data['sku']
        
        # ショップ名
        if 'shop_name' in js_data:
            item_details['shopName'] = js_data['shop_name']
        elif 'shopName' in js_data:
            item_details['shopName'] = js_data['shopName']
        
        # 画像URL
        if 'image_url' in js_data:
            item_details['imageUrl'] = js_data['image_url']
        elif 'image' in js_data:
            item_details['imageUrl'] = js_data['image']
        
        # その他の情報をすべて追加
        for key, value in js_data.items():
            if key not in item_details and isinstance(value, (str, int, float, bool)):
                item_details[key] = value
        
        return item_details

    def get_item_details_from_url(self, url, progress_callback=None):
        """
        URLから商品詳細情報を取得
        
        Args:
            url (str): 商品ページのURL
            progress_callback (function, optional): 進捗コールバック関数
            
        Returns:
            dict: 商品詳細情報
        """
        try:
            print(f"URLから商品詳細を取得: {url}")
            
            # URLから商品コードを抽出
            item_code = self.extract_item_code_from_url(url)
            if not item_code:
                print(f"URLから商品コードを抽出できませんでした: {url}")
                # URLをそのまま使用して情報を取得
                js_data = self.extract_js_data_from_url(url)
                if js_data:
                    print("JavaScriptデータから情報を取得します")
                    return self.extract_item_details_from_js(js_data, url)
                else:
                    print("JavaScriptデータの取得に失敗しました")
                    return {"error": "商品情報を取得できませんでした"}
            
            # 商品コードを使用してAPIから情報を取得
            print(f"商品コード {item_code} を使用してAPIから情報を取得")
            api_data = self.get_item_by_id(item_code)
            
            # APIから情報が取得できない場合はJavaScriptデータを使用
            if not api_data or 'error' in api_data:
                print(f"APIからの情報取得に失敗。JavaScriptデータを使用します: {api_data}")
                js_data = self.extract_js_data_from_url(url)
                if js_data:
                    return self.extract_item_details_from_js(js_data, url)
                else:
                    return {"error": "商品情報を取得できませんでした"}
            
            return api_data
        except Exception as e:
            print(f"商品詳細の取得中にエラーが発生: {e}")
            traceback.print_exc()
            return {"error": f"エラー: {str(e)}"}

    def extract_info_from_html(self, url):
        """
        HTMLから商品情報を直接抽出
        
        Args:
            url (str): 商品ページのURL
            
        Returns:
            dict: 商品情報
        """
        if self.driver is None:
            rakuten_init = RakutenInit(self.application_id)
            rakuten_init.initialize_selenium()
            self.driver = rakuten_init.driver
        
        try:
            self.driver.get(url)
            time.sleep(3)  # ページ読み込み待機
            
            item_info = {
                "itemUrl": url,
                "source": "html"
            }
            
            # 商品名を取得
            try:
                item_name_elem = self.driver.find_element(By.CSS_SELECTOR, "span.item_name, h1.item_name, h1.item-name")
                item_info["itemName"] = item_name_elem.text.strip()
            except:
                try:
                    item_name_elem = self.driver.find_element(By.CSS_SELECTOR, "h1, h2.item-name")
                    item_info["itemName"] = item_name_elem.text.strip()
                except:
                    item_info["itemName"] = "不明"
            
            # 価格を取得
            try:
                price_elem = self.driver.find_element(By.CSS_SELECTOR, "span.price, p.price, div.price")
                price_text = price_elem.text.strip()
                # 数値以外の文字を削除
                price_str = re.sub(r'[^\d]', '', price_text)
                if price_str:
                    item_info["itemPrice"] = int(price_str)
            except:
                item_info["itemPrice"] = 0
            
            # ショップ名を取得
            try:
                shop_elem = self.driver.find_element(By.CSS_SELECTOR, "span.shop_name, div.shop_name")
                item_info["shopName"] = shop_elem.text.strip()
            except:
                item_info["shopName"] = "不明"
            
            # 画像URLを取得
            try:
                img_elem = self.driver.find_element(By.CSS_SELECTOR, "div.image_main img")
                item_info["imageUrl"] = img_elem.get_attribute("src")
            except:
                item_info["imageUrl"] = ""
            
            return item_info
        except Exception as e:
            print(f"HTMLからの情報抽出中にエラー: {e}")
            return {"error": f"HTMLからの情報抽出に失敗: {str(e)}"}

    def get_item_by_url(self, url):
        """
        URLから商品情報を取得
        
        Args:
            url (str): 商品ページのURL
            
        Returns:
            dict: 商品情報
        """
        if self.driver is None:
            rakuten_init = RakutenInit(self.application_id)
            rakuten_init.initialize_selenium()
            self.driver = rakuten_init.driver
        
        try:
            print(f"商品ページにアクセス中: {url}")
            self.driver.get(url)
            time.sleep(5)  # ページ読み込み待機を長めに
            
            # 商品情報を格納する辞書
            item_info = {
                "itemUrl": url,
                "source": "direct_scrape"
            }
            
            # 商品名を取得
            try:
                selectors = [
                    "h1.item_name", 
                    "h1.item-name", 
                    "span.item_name", 
                    "div.item-name", 
                    "h1", 
                    "h2.item-name"
                ]
                
                for selector in selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            item_info["itemName"] = elements[0].text.strip()
                            print(f"商品名を取得: {item_info['itemName']}")
                            break
                    except:
                        continue
                    
                if "itemName" not in item_info:
                    item_info["itemName"] = "不明"
                    print("商品名を取得できませんでした")
            except Exception as e:
                print(f"商品名取得中にエラー: {e}")
                item_info["itemName"] = "不明"
            
            # 価格を取得
            try:
                price_selectors = [
                    "span.price", 
                    "p.price", 
                    "div.price", 
                    "span.price--OX_YW", 
                    "span[data-test='price']",
                    "span.important"
                ]
                
                for selector in price_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            price_text = elements[0].text.strip()
                            # 数値以外の文字を削除
                            price_str = re.sub(r'[^\d]', '', price_text)
                            if price_str:
                                item_info["itemPrice"] = int(price_str)
                                print(f"価格を取得: {item_info['itemPrice']}")
                                break
                    except:
                        continue
                    
                if "itemPrice" not in item_info:
                    item_info["itemPrice"] = 0
                    print("価格を取得できませんでした")
            except Exception as e:
                print(f"価格取得中にエラー: {e}")
                item_info["itemPrice"] = 0
            
            # ショップ名を取得
            try:
                shop_selectors = [
                    "span.shop_name", 
                    "div.shop_name", 
                    "a.shop-name", 
                    "span.shop-name"
                ]
                
                for selector in shop_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            item_info["shopName"] = elements[0].text.strip()
                            print(f"ショップ名を取得: {item_info['shopName']}")
                            break
                    except:
                        continue
                    
                if "shopName" not in item_info:
                    item_info["shopName"] = "不明"
                    print("ショップ名を取得できませんでした")
            except Exception as e:
                print(f"ショップ名取得中にエラー: {e}")
                item_info["shopName"] = "不明"
            
            # 商品コードを取得（ページのHTMLから直接探す）
            try:
                page_source = self.driver.page_source
                # 商品コードを探すパターン
                patterns = [
                    r'商品コード[：:]\s*([A-Za-z0-9\-_]+)',
                    r'商品番号[：:]\s*([A-Za-z0-9\-_]+)',
                    r'商品ID[：:]\s*([A-Za-z0-9\-_]+)',
                    r'item_id\s*=\s*[\'"]([A-Za-z0-9\-_]+)[\'"]',
                    r'itemCode\s*=\s*[\'"]([A-Za-z0-9\-_]+)[\'"]'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, page_source)
                    if match:
                        item_info["itemCode"] = match.group(1)
                        print(f"商品コードを取得: {item_info['itemCode']}")
                        break
                    
                if "itemCode" not in item_info:
                    # URLから抽出を試みる
                    item_code = self.extract_item_code_from_url(url)
                    if item_code:
                        item_info["itemCode"] = item_code
                        print(f"URLから商品コードを抽出: {item_code}")
                    else:
                        item_info["itemCode"] = "不明"
                        print("商品コードを取得できませんでした")
            except Exception as e:
                print(f"商品コード取得中にエラー: {e}")
                item_info["itemCode"] = "不明"
            
            # JavaScriptデータも取得して補完
            try:
                js_data = self.extract_js_data_from_url(url)
                if js_data:
                    print("JavaScriptデータを取得しました")
                    # 不足している情報を補完
                    for key, value in js_data.items():
                        if key not in item_info and isinstance(value, (str, int, float, bool)):
                            item_info[key] = value
            except Exception as e:
                print(f"JavaScriptデータ取得中にエラー: {e}")
            
            return item_info
        except Exception as e:
            print(f"商品情報取得中にエラー: {e}")
            traceback.print_exc()
            return {"error": f"エラー: {str(e)}"}

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