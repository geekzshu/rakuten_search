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


class RakutenItemInfo:
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
                print(js_data)
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
                return result['Items'][0]
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
                    return result['Items'][0]
                else:
                    return None
        except Exception as e:
            print(f"API呼び出し中にエラー: {e}")
            return None
    
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
                print("画像を取得中...")
                
                # ページが完全に読み込まれるのを待つ
                time.sleep(2)
                
                # JavaScriptを実行して遅延読み込み画像を表示させる
                self.driver.execute_script("""
                    // 画面をスクロールして遅延読み込み画像を表示
                    window.scrollTo(0, document.body.scrollHeight / 2);
                    setTimeout(() => { window.scrollTo(0, 0); }, 500);
                """)
                time.sleep(2)
                
                # 画像要素を取得（複数のセレクタを試す）
                image_selectors = [
                    ".image--3z5RH",  # 元のクラス名
                    "img.itemphoto",  # 商品画像の一般的なクラス
                    ".rakuten-card-item-image img",  # 楽天カードの商品画像
                    ".galleryImage img",  # ギャラリー画像
                    ".imageContainer img",  # 画像コンテナ
                    ".imageThumbnail img",  # サムネイル画像
                    "div.image_main img",  # メイン画像
                    ".item-image-container img"  # 商品画像コンテナ
                ]
                
                image_urls = []
                
                for selector in image_selectors:
                    try:
                        image_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        if image_elements:
                            print(f"{selector} クラスの画像要素が {len(image_elements)} 個見つかりました")
                            
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
                        
                        if image_urls:
                            break  # 画像が見つかったらループを終了
                    except Exception as e:
                        print(f"セレクタ {selector} での画像検索中にエラー: {e}")
                        continue
                
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
            
            except Exception as e:
                print(f"画像取得処理中にエラーが発生しました: {e}")
            
        except Exception as e:
            print(f"追加情報の取得中にエラーが発生しました: {e}")
            traceback.print_exc()
            
        return additional_info
    
    def get_reviews_from_page(self, item_url):
        """
        商品ページからレビュー情報を取得
        
        Args:
            item_url (str): 商品ページのURL
            
        Returns:
            dict: レビュー情報（件数、レビューテキスト一覧）
        """
        if self.driver is None:
            rakuten_init = RakutenInit(self.application_id)
            rakuten_init.initialize_selenium()
            self.driver = rakuten_init.driver
        
        try:
            print(f"商品ページにアクセス: {item_url}")
            self.driver.get(item_url)
            time.sleep(3)  # ページ読み込み待機
            
            # レビューボタンまたはレビューURLを探す
            review_button = None
            review_count = 0
            review_url = None
            
            try:
                # 新しいレビューボタンのセレクタを試す
                review_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='review.rakuten.co.jp']")
                if review_elements:
                    review_url = review_elements[0].get_attribute('href')
                    print(f"レビューURL発見: {review_url}")
                
                # 別のセレクタも試す
                if not review_url:
                    review_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'review') or contains(text(), 'レビュー')]")
                    for link in review_links:
                        href = link.get_attribute('href')
                        if href and 'review' in href:
                            review_url = href
                            print(f"代替方法でレビューURL発見: {review_url}")
                            break
            except Exception as e:
                print(f"レビューボタン/URL検索中にエラー: {e}")
            
            # レビューページに移動
            if review_url:
                print(f"レビューページに直接アクセス: {review_url}")
                self.driver.get(review_url)
                time.sleep(5)  # ページ読み込み待機
            
            # レビュー一覧を取得
            reviews = []
            max_reviews = 20  # 取得する最大レビュー数
            
            try:
                # 提供されたHTMLに基づくセレクタ
                review_containers = self.driver.find_elements(By.CSS_SELECTOR, "li > div.spacer--xFAdr.full-width--2JiOP")
                
                if review_containers:
                    print(f"{len(review_containers)}件のレビュー要素を発見")
                    
                    for container in review_containers[:max_reviews]:
                        try:
                            # 評価を取得
                            rating_elem = container.find_elements(By.CSS_SELECTOR, "span.text-container--IAFCr")
                            rating = 0
                            if rating_elem:
                                try:
                                    rating = float(rating_elem[0].text)
                                except ValueError:
                                    pass
                            
                            # 日付を取得
                            date_elem = container.find_elements(By.CSS_SELECTOR, "div.text-display--1Iony.type-body--1W5uC.size-small--sv6IW.color-gray-dark--2N4Oj")
                            date = ""
                            if date_elem:
                                date = date_elem[0].text
                            
                            # レビュータイトルを取得
                            title_elem = container.find_elements(By.CSS_SELECTOR, "div.text-display--1Iony.type-header--18XjX")
                            title = ""
                            if title_elem:
                                title = title_elem[0].text
                            
                            # レビュー本文を取得
                            comment_elem = container.find_elements(By.CSS_SELECTOR, "div.review-body--1pESv")
                            if not comment_elem:
                                comment_elem = container.find_elements(By.CSS_SELECTOR, "div.no-ellipsis--IKXkO")
                            
                            comment = ""
                            if comment_elem:
                                comment = comment_elem[0].text
                            
                            if comment:
                                reviews.append({
                                    "rating": rating,
                                    "title": title,
                                    "comment": comment,
                                    "date": date
                                })
                        except Exception as e:
                            print(f"レビュー要素の解析中にエラー: {e}")
                
                # 次のページがあれば取得（最大2ページまで）
                if reviews and len(reviews) < max_reviews:
                    try:
                        next_page_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='page=2']")
                        if not next_page_links:
                            next_page_links = self.driver.find_elements(By.XPATH, "//a[contains(text(), '次へ') or contains(text(), '次の') or contains(@class, 'next')]")
                        
                        if next_page_links:
                            next_url = next_page_links[0].get_attribute('href')
                            if next_url:
                                print(f"次のページに移動: {next_url}")
                                self.driver.get(next_url)
                                time.sleep(3)
                                
                                # 2ページ目のレビューを取得
                                page2_containers = self.driver.find_elements(By.CSS_SELECTOR, "li > div.spacer--xFAdr.full-width--2JiOP")
                                
                                if page2_containers:
                                    print(f"2ページ目で{len(page2_containers)}件のレビュー要素を発見")
                                    
                                    for container in page2_containers[:max_reviews - len(reviews)]:
                                        try:
                                            # 評価を取得
                                            rating_elem = container.find_elements(By.CSS_SELECTOR, "span.text-container--IAFCr")
                                            rating = 0
                                            if rating_elem:
                                                try:
                                                    rating = float(rating_elem[0].text)
                                                except ValueError:
                                                    pass
                                            
                                            # 日付を取得
                                            date_elem = container.find_elements(By.CSS_SELECTOR, "div.text-display--1Iony.type-body--1W5uC.size-small--sv6IW.color-gray-dark--2N4Oj")
                                            date = ""
                                            if date_elem:
                                                date = date_elem[0].text
                                            
                                            # レビュータイトルを取得
                                            title_elem = container.find_elements(By.CSS_SELECTOR, "div.text-display--1Iony.type-header--18XjX")
                                            title = ""
                                            if title_elem:
                                                title = title_elem[0].text
                                            
                                            # レビュー本文を取得
                                            comment_elem = container.find_elements(By.CSS_SELECTOR, "div.review-body--1pESv")
                                            if not comment_elem:
                                                comment_elem = container.find_elements(By.CSS_SELECTOR, "div.no-ellipsis--IKXkO")
                                            
                                            comment = ""
                                            if comment_elem:
                                                comment = comment_elem[0].text
                                            
                                            if comment:
                                                reviews.append({
                                                    "rating": rating,
                                                    "title": title,
                                                    "comment": comment,
                                                    "date": date
                                                })
                                        except Exception as e:
                                            print(f"2ページ目のレビュー要素の解析中にエラー: {e}")
                    except Exception as e:
                        print(f"次のページの取得中にエラー: {e}")
            
            except Exception as e:
                print(f"レビュー解析中にエラー: {e}")
            
            print(f"合計 {len(reviews)} 件のレビューを取得しました")
            return {
                "review_count": len(reviews),
                "reviews": reviews
            }
        
        except Exception as e:
            print(f"レビュー取得中にエラー: {e}")
            return {"review_count": 0, "reviews": []}
    
    def analyze_item(self, url):
        """
        商品ページのURLから商品情報と追加情報を取得
        
        Args:
            url (str): 商品ページのURL
            
        Returns:
            dict: 商品情報と追加情報を含む辞書
        """
        try:
            # 1. JavaScriptデータを取得してitemidを抽出
            js_data = self.extract_js_data_from_url(url)
            
            if not js_data or 'itemid' not in js_data:
                print(f"URLからitemidを抽出できませんでした: {url}")
                return {"url": url, "error": "itemidを抽出できませんでした"}
            
            item_id = js_data['itemid']
            print(f"抽出したitemid: {item_id}")
            
            # 2. 楽天APIで商品情報を取得
            api_item_info = self.get_item_by_id(item_id)
            
            if not api_item_info:
                print(f"APIから商品情報を取得できませんでした: {item_id}")
                api_item_info = {}
            
            # 3. 追加情報を取得
            additional_info = self.get_additional_info(url)
            
            # 4. レビュー情報を取得
            print(f"レビュー情報を取得中: {url}")
            review_info = self.get_reviews_from_page(url)
            
            # 結果を統合
            result = {
                "url": url,
                "itemId": item_id,
                "detailed_review_count": review_info['review_count'],
                "reviews": review_info['reviews']
            }
            
            # APIからの情報を追加
            if api_item_info:
                for key, value in api_item_info.items():
                    result[f"api_{key}"] = value
            
            # 追加情報を追加
            for key, value in additional_info.items():
                result[key] = value
            
            return result
            
        except Exception as e:
            print(f"商品分析中にエラーが発生しました: {e}")
            traceback.print_exc()
            return {"url": url, "error": str(e)}
    
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
            
            # URLを分析
            item_result = self.analyze_item(url)
            results.append(item_result)
            
            # 少し待機して連続アクセスを避ける
            time.sleep(2)
        
        if progress_callback:
            progress_callback(len(urls), len(urls), "処理完了")
        
        # 結果をデータフレームに変換
        if results:
            df = pd.DataFrame(results)
            
            # レビューテキストを別の列に展開
            if 'reviews' in df.columns:
                # レビューの最初の5件を別々の列に展開
                max_reviews = 0
                for reviews in df['reviews']:
                    if isinstance(reviews, list):
                        max_reviews = max(max_reviews, len(reviews))
                
                for i in range(min(20, max_reviews)):
                    df[f'review_{i+1}_rating'] = df['reviews'].apply(
                        lambda reviews: reviews[i]['rating'] if isinstance(reviews, list) and i < len(reviews) else None
                    )
                    df[f'review_{i+1}_title'] = df['reviews'].apply(
                        lambda reviews: reviews[i]['title'] if isinstance(reviews, list) and i < len(reviews) else None
                    )
                    df[f'review_{i+1}_comment'] = df['reviews'].apply(
                        lambda reviews: reviews[i]['comment'] if isinstance(reviews, list) and i < len(reviews) else None
                    )
                    df[f'review_{i+1}_date'] = df['reviews'].apply(
                        lambda reviews: reviews[i]['date'] if isinstance(reviews, list) and i < len(reviews) else None
                    )
                
                # 元のreviewsリストは削除（データフレームを軽くするため）
                df = df.drop(columns=['reviews'])
            
            return df
        else:
            return pd.DataFrame()
    
    def save_results(self, df, filename="rakuten_item_info.xlsx"):
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
    APPLICATION_ID = "1084639123280921528"  # 実際のアプリケーションIDに変更してください
    
    # 取得したい商品ページのURLリスト
    URLS = [
        "https://item.rakuten.co.jp/cosme-de/j4580107383314/",
        "https://item.rakuten.co.jp/cosmeland/4589596694672/",
        "https://item.rakuten.co.jp/shop-beautiful-garden/clayshampoot2set/"
    ]
    
    # 商品情報取得ツールの初期化
    info_tool = RakutenItemInfo(APPLICATION_ID)
    
    try:
        # 商品情報の取得と分析
        results = info_tool.process_urls(URLS)
        
        # 結果の表示
        if not results.empty:
            print("\n===== 商品情報のサンプル =====")
            # カラム名を確認
            print("利用可能なカラム:", results.columns.tolist())
            
            # 主要な情報を表示
            display_columns = ['url', 'itemId', 'js_price', 'rating', 'reviewCount', 'detailed_review_count']
            available_columns = [col for col in display_columns if col in results.columns]
            
            # レビュー情報が存在する場合は最初のレビューも表示
            if 'review_1_comment' in results.columns:
                available_columns.extend(['review_1_rating', 'review_1_title', 'review_1_comment'])
                
            print(results[available_columns])
            
            # 結果の保存
            info_tool.save_results(results, "rakuten_item_info.xlsx")
        
    finally:
        # リソースの解放
        info_tool.close() 