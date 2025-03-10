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


class RakutenCompetitorAnalysis:
    def __init__(self, application_id):
        """
        楽天市場の競合調査ツールの初期化
        
        Args:
            application_id (str): RAKUTEN_API_KEY
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
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            print(f"ChromeDriverManagerでのインストールに失敗: {e}")
            # 失敗した場合はローカルのChromeDriverを使用
            service = Service("./chromedriver_m")
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
    def search_similar_items(self, keyword, hits=30, page=1, sort="-reviewAverage"):
        """
        キーワードに基づいて類似商品を検索
        
        Args:
            keyword (str): 検索キーワード
            hits (int): 1ページあたりの取得件数
            page (int): ページ番号
            sort (str): ソート順（例: "-reviewAverage"はレビュー評価の高い順）
            
        Returns:
            dict: API応答
        """
        params = {
            "applicationId": self.application_id,
            "keyword": keyword,
            "hits": hits,
            "page": page,
            "sort": sort,
            "formatVersion": 2
        }
        
        response = requests.get(self.base_url, params=params)
        return response.json()
    
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
        time.sleep(3)  # ページ読み込み待機時間を増やす
        
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
                
            # 商品説明の取得（複数のセレクタを試す）
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
                
            # 販売者情報の取得（複数のセレクタを試す）
            seller_selectors = [
                "div.seller-info",
                "div.shopInfo",
                "div#shopInfo",
                "div.shop-info"
            ]
            
            for selector in seller_selectors:
                try:
                    seller_info = self.driver.find_element(By.CSS_SELECTOR, selector).text
                    if seller_info:
                        additional_info['seller_info'] = seller_info
                        break
                except:
                    continue
            
            if 'seller_info' not in additional_info:
                additional_info['seller_info'] = "販売者情報が見つかりません"
                
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
    
    def get_reviews_from_page(self, item_url):
        """
        商品ページからレビュー情報を取得
        
        Args:
            item_url (str): 商品ページのURL
            
        Returns:
            dict: レビュー情報（件数、レビューテキスト一覧）
        """
        if self.driver is None:
            self.initialize_selenium()
        
        try:
            # 商品ページにアクセス
            self.driver.get(item_url)
            time.sleep(2)  # ページ読み込み待機
            
            # レビューボタンを探す
            review_buttons = self.driver.find_elements(By.CSS_SELECTOR, "a.button--3SNaj")
            review_button = None
            review_count = 0
            
            # レビューボタンを特定
            for button in review_buttons:
                if "レビュー" in button.text:
                    text = button.text.strip()
                    # レビュー件数を抽出
                    match = re.search(r'(\d+)', text)
                    if match:
                        review_count = int(match.group(1))
                    review_button = button
                    break
            
            if not review_button or review_count == 0:
                return {"review_count": 0, "reviews": []}
            
            # レビューページに移動
            review_button.click()
            time.sleep(3)  # ページ読み込み待機
            
            # レビュー一覧を取得
            reviews = []
            review_elements = self.driver.find_elements(By.CSS_SELECTOR, "ul.itemReviewList > li")
            
            for review_element in review_elements:
                try:
                    # レビュー評価
                    rating_element = review_element.find_element(By.CSS_SELECTOR, "span.revRating")
                    rating = float(rating_element.text.replace("点", "").strip()) if rating_element else 0
                    
                    # レビュータイトル
                    title_element = review_element.find_element(By.CSS_SELECTOR, "div.revTitleBox span")
                    title = title_element.text.strip() if title_element else ""
                    
                    # レビュー本文
                    comment_element = review_element.find_element(By.CSS_SELECTOR, "dd.revComment")
                    comment = comment_element.text.strip() if comment_element else ""
                    
                    # レビュー日付
                    date_element = review_element.find_element(By.CSS_SELECTOR, "p.revDate")
                    date = date_element.text.strip() if date_element else ""
                    
                    reviews.append({
                        "rating": rating,
                        "title": title,
                        "comment": comment,
                        "date": date
                    })
                except Exception as e:
                    print(f"レビュー要素の解析中にエラー: {e}")
                    continue
            
            return {
                "review_count": review_count,
                "reviews": reviews
            }
        
        except Exception as e:
            print(f"レビュー取得中にエラー: {e}")
            return {"review_count": 0, "reviews": []}
    
    def analyze_competitors(self, keyword, max_items=10, sort_order="-reviewAverage", progress_callback=None, headless=True):
        """
        競合分析を実行し、結果をデータフレームとして返す
        
        Args:
            keyword (str): 検索キーワード
            max_items (int): 分析する最大商品数
            sort_order (str): ソート順（デフォルトはレビュー評価の高い順）
            progress_callback (callable): 進捗を報告するコールバック関数
            headless (bool): ヘッドレスモードで実行するかどうか
            
        Returns:
            pandas.DataFrame: 競合分析結果
        """
        if progress_callback:
            progress_callback(0, max_items, f"「{keyword}」の競合分析を開始します...")
        else:
            print(f"「{keyword}」の競合分析を開始します...")
        
        print(f"ソート順: {sort_order}")
        
        # APIから商品情報を取得
        api_result = self.search_similar_items(keyword, hits=max_items, sort=sort_order)
        
        # デバッグ用にAPIレスポンスの構造を確認
        print("APIレスポンス構造:", json.dumps(api_result, indent=2, ensure_ascii=False)[:500] + "...")
        
        if 'Items' not in api_result:
            if progress_callback:
                progress_callback(0, max_items, "商品が見つかりませんでした。")
            print("商品が見つかりませんでした。")
            return pd.DataFrame()
        
        items = api_result['Items']
        if progress_callback:
            progress_callback(0, len(items), f"{len(items)}件の商品が見つかりました。詳細情報を取得中...")
        else:
            print(f"{len(items)}件の商品が見つかりました。詳細情報を取得中...")
        
        # 結果を格納するリスト
        results = []
        
        # Seleniumの初期化
        if self.driver is None:
            self.initialize_selenium(headless=headless)
        
        # 各商品の詳細情報を取得
        for i, item_data in enumerate(items):
            # formatVersion=2の場合、直接itemデータが含まれている可能性があります
            if isinstance(item_data, dict) and 'Item' in item_data:
                item = item_data['Item']
            else:
                # 直接itemデータとして扱う
                item = item_data
            
            if progress_callback:
                progress_callback(i+1, len(items), f"商品 {i+1}/{len(items)} の情報を取得中: {item.get('itemName', '不明')[:30]}...")
            else:
                print(f"商品 {i+1}/{len(items)} の情報を取得中: {item.get('itemName', '不明')[:30]}...")
            
            # デバッグ: 商品データの構造を確認
            if i == 0:  # 最初の商品だけ詳細を出力
                print(f"商品データ構造: {json.dumps(item, indent=2, ensure_ascii=False)[:500]}...")
                if 'mediumImageUrls' in item:
                    print(f"mediumImageUrls型: {type(item['mediumImageUrls'])}")
                    print(f"mediumImageUrls内容: {item['mediumImageUrls']}")
            
            # APIから取得した基本情報
            item_info = {
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
                
                # 全ての画像URLを取得（最大20枚）
                all_image_urls = []
                
                # mediumImageUrlsから全ての画像を取得
                if medium_image_urls:
                    if isinstance(medium_image_urls, list):
                        for img in medium_image_urls:
                            if isinstance(img, dict) and 'imageUrl' in img:
                                all_image_urls.append(img['imageUrl'])
                            elif isinstance(img, str):
                                all_image_urls.append(img)
                    elif isinstance(medium_image_urls, str):
                        all_image_urls.append(medium_image_urls)
                
                # 追加の画像URLがある場合（APIによって異なる形式で返される可能性がある）
                additional_images = item.get('mediumImageUrls', [])
                if isinstance(additional_images, list) and additional_images != medium_image_urls:
                    for img in additional_images:
                        if isinstance(img, dict) and 'imageUrl' in img:
                            all_image_urls.append(img['imageUrl'])
                        elif isinstance(img, str):
                            all_image_urls.append(img)
                
                # 重複を削除
                all_image_urls = list(dict.fromkeys(all_image_urls))
                
                # 全ての画像URLをカンマ区切りで保存
                item_info['allImageUrls'] = '|'.join(all_image_urls)
                
                # 画像の枚数を保存
                item_info['imageCount'] = len(all_image_urls)
                
                print(f"取得した画像数: {len(all_image_urls)}")
                
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
        
        print("競合分析が完了しました。")
        return df
    
    def save_results(self, df, filename="rakuten_competitor_analysis.xlsx"):
        """
        分析結果をファイルに保存
        
        Args:
            df (pandas.DataFrame): 保存するデータフレーム
            filename (str): 保存するファイル名
        """
        try:
            # Excelファイルとして保存を試みる
            df.to_excel(filename, index=False)
            print(f"分析結果を {filename} に保存しました。")
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

    def search_and_analyze(self, keyword, max_items=10, sort="-reviewAverage"):
        """
        キーワードで検索して競合分析を行う
        
        Args:
            keyword (str): 検索キーワード
            max_items (int): 取得する商品数
            sort (str): ソート順
            
        Returns:
            pandas.DataFrame: 分析結果
        """
        # 初期化
        all_items = []
        page = 1
        items_per_page = min(30, max_items)
        
        # 商品情報の取得
        while len(all_items) < max_items:
            print(f"ページ {page} の商品を取得中...")
            result = self.search_similar_items(keyword, hits=items_per_page, page=page, sort=sort)
            
            if 'Items' not in result or not result['Items']:
                break
            
            items = result['Items']
            all_items.extend(items[:max_items - len(all_items)])
            
            if len(items) < items_per_page:
                break
            
            page += 1
        
        # 結果の整形
        formatted_items = []
        
        for i, item_data in enumerate(all_items):
            if isinstance(item_data, dict) and 'Item' in item_data:
                item = item_data['Item']
            else:
                item = item_data
            
            # 基本情報の抽出
            item_info = {
                'itemName': item.get('itemName', ''),
                'itemPrice': item.get('itemPrice', 0),
                'itemUrl': item.get('itemUrl', ''),
                'shopName': item.get('shopName', ''),
                'shopUrl': item.get('shopUrl', ''),
                'itemCode': item.get('itemCode', ''),
                'imageUrl': item.get('mediumImageUrls', [{}])[0].get('imageUrl', '') if item.get('mediumImageUrls') else '',
                'reviewAverage': item.get('reviewAverage', 0),
                'reviewCount': item.get('reviewCount', 0),
                'pointRate': item.get('pointRate', 0),
                'pointRateStartTime': item.get('pointRateStartTime', ''),
                'pointRateEndTime': item.get('pointRateEndTime', ''),
                'shopAffiliateUrl': item.get('shopAffiliateUrl', ''),
                'affiliateRate': item.get('affiliateRate', 0),
                'shipOverseasFlag': item.get('shipOverseasFlag', 0),
                'asurakuFlag': item.get('asurakuFlag', 0),
                'taxFlag': item.get('taxFlag', 0),
                'postageFlag': item.get('postageFlag', 0),
                'creditCardFlag': item.get('creditCardFlag', 0),
                'shopOfTheYearFlag': item.get('shopOfTheYearFlag', 0),
                'giftFlag': item.get('giftFlag', 0),
                'position': i + 1,
                'keyword': keyword
            }
            
            # 追加のレビュー情報を取得
            print(f"商品 {i+1}/{len(all_items)} のレビュー情報を取得中...")
            review_info = self.get_reviews_from_page(item_info['itemUrl'])
            
            # レビュー情報を追加
            item_info['detailed_review_count'] = review_info['review_count']
            item_info['reviews'] = review_info['reviews']
            
            formatted_items.append(item_info)
        
        # DataFrameに変換
        df = pd.DataFrame(formatted_items)
        
        # レビューテキストを別の列に展開
        if not df.empty and 'reviews' in df.columns:
            # レビューの最初の5件を別々の列に展開
            for i in range(min(5, max(len(reviews) for reviews in df['reviews'] if isinstance(reviews, list)))):
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

# 使用例
if __name__ == "__main__":
    # 楽天APIのアプリケーションIDを設定
    APPLICATION_ID = "1084639123280921528"
    
    # 分析したい商品のキーワード
    KEYWORD = "クレイクリームシャンプー"
    
    # ソート順の設定（レビュー評価の高い順）
    SORT_ORDER = "-reviewAverage"
    
    # 競合分析ツールの初期化
    analyzer = RakutenCompetitorAnalysis(APPLICATION_ID)
    
    try:
        # 競合分析の実行（満足度順）
        results = analyzer.analyze_competitors(KEYWORD, max_items=10, sort_order=SORT_ORDER)
        
        # 結果の表示
        if not results.empty:
            print("\n===== 分析結果のサンプル =====")
            # カラム名を確認
            print("利用可能なカラム:", results.columns.tolist())
            
            # review_countカラムが存在するか確認し、存在しない場合は代替カラムを使用
            display_columns = ['itemName', 'itemPrice', 'shopName', 'reviewAverage']
            if 'review_count' in results.columns:
                display_columns.append('review_count')
            elif 'reviewCount' in results.columns:
                display_columns.append('reviewCount')
            
            print(results[display_columns].head())
            
            # 結果の保存
            analyzer.save_results(results, f"rakuten_{KEYWORD}_analysis.xlsx")
            
            # 価格帯の分析
            price_stats = results['itemPrice'].describe()
            print("\n===== 価格統計 =====")
            print(f"最低価格: {price_stats['min']}円")
            print(f"最高価格: {price_stats['max']}円")
            print(f"平均価格: {price_stats['mean']:.2f}円")
            print(f"中央価格: {price_stats['50%']}円")
            
            # レビュー評価の分析
            if 'rating' in results.columns:
                rating_stats = results['rating'].describe()
                print("\n===== レビュー評価統計 =====")
                print(f"平均評価: {rating_stats['mean']:.2f}点")
                print(f"最高評価: {rating_stats['max']}点")
                print(f"最低評価: {rating_stats['min']}点")
    
    finally:
        # リソースの解放
        analyzer.close() 