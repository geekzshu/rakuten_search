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
import matplotlib.pyplot as plt
import matplotlib as mpl

# 日本語フォント設定（japanize_matplotlibを使わない方法）
try:
    # macOSの場合
    plt.rcParams['font.family'] = 'Hiragino Sans GB'
except Exception:
    try:
        # Windowsの場合
        plt.rcParams['font.family'] = 'MS Gothic'
    except Exception:
        try:
            # Linuxの場合
            plt.rcParams['font.family'] = 'IPAGothic'
        except Exception:
            print("日本語フォントの設定に失敗しました。グラフの日本語が文字化けする可能性があります。")

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
        
        # Streamlit Cloud環境用の設定
        is_streamlit_cloud = os.environ.get('STREAMLIT_SHARING', '') or os.environ.get('STREAMLIT_CLOUD', '')
        
        if is_streamlit_cloud:
            # Streamlit Cloud環境ではChromiumのパスを明示的に指定
            chrome_options.binary_location = "/usr/bin/chromium-browser"
            
            # 環境変数も設定
            os.environ['CHROME_PATH'] = '/usr/bin/chromium-browser'
            os.environ['CHROMEDRIVER_PATH'] = '/usr/bin/chromedriver'
        
        try:
            # 最新のwebdriver-managerでは、versionパラメータが削除されている
            from webdriver_manager.chrome import ChromeDriverManager
            
            try:
                # ChromeTypeを使用する方法を試す
                try:
                    from webdriver_manager.core.utils import ChromeType
                    service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
                except ImportError:
                    try:
                        from webdriver_manager.core.os_manager import ChromeType
                        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
                    except ImportError:
                        # ChromeTypeが見つからない場合は、chrome_typeなしで実行
                        service = Service(ChromeDriverManager().install())
            except Exception as e:
                print(f"ChromeTypeでのインストールに失敗: {e}")
                # バージョン指定なしで最新を取得
                service = Service(ChromeDriverManager().install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
        except Exception as e:
            print(f"ChromeDriverManagerでのインストールに失敗: {e}")
            # 代替方法を試す...
        
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
            
            # 追加のレビュー情報を取得
            if progress_callback:
                # 正しい引数の順序と数で呼び出す
                current_progress = i + 1
                total_items = len(items)
                message = f"商品 {current_progress}/{total_items} のレビュー情報を取得中..."
                progress_callback(current_progress, total_items, message)
            else:
                print(f"商品 {i+1}/{len(items)} のレビュー情報を取得中...")

            review_info = self.get_reviews_from_page(item_info['itemUrl'])

            # レビュー情報を追加
            item_info['detailed_review_count'] = review_info['review_count']
            item_info['reviews'] = review_info['reviews']
            
            results.append(item_info)
            
            # APIの制限に引っかからないよう少し待機
            time.sleep(1)
        
        # Seleniumドライバーを閉じる
        if self.driver:
            self.driver.quit()
            self.driver = None
        
        # 結果をデータフレームに変換
        df = pd.DataFrame(results)
        
        # レビューテキストを別の列に展開
        if not df.empty and 'reviews' in df.columns:
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

    def save_reviews_to_csv(self, df, keyword, output_dir="output"):
        """
        レビュー情報を専用のCSVファイルに保存
        
        Args:
            df (pandas.DataFrame): 商品情報を含むデータフレーム
            keyword (str): 検索キーワード
            output_dir (str): 出力ディレクトリ
            
        Returns:
            str: 保存したファイルのパス
        """
        try:
            # 出力ディレクトリが存在しない場合は作成
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
            
            # 現在の日時を取得してファイル名に使用
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            # レビュー情報を抽出
            review_data = []
            
            for i, row in df.iterrows():
                item_name = row.get('itemName', '不明')
                shop_name = row.get('shopName', '不明')
                
                # レビュー列を探す
                for j in range(1, 21):  # 最大20件のレビュー
                    rating_col = f'review_{j}_rating'
                    title_col = f'review_{j}_title'
                    comment_col = f'review_{j}_comment'
                    date_col = f'review_{j}_date'
                    
                    if all(col in row for col in [rating_col, title_col, comment_col, date_col]):
                        if pd.notna(row[comment_col]) and row[comment_col]:
                            review_data.append({
                                'keyword': keyword,
                                'item_name': item_name,
                                'shop_name': shop_name,
                                'review_rating': row.get(rating_col),
                                'review_title': row.get(title_col),
                                'review_comment': row.get(comment_col),
                                'review_date': row.get(date_col)
                            })
            
            if not review_data:
                print("保存するレビュー情報がありません。")
                return None
            
            # レビューデータをデータフレームに変換
            reviews_df = pd.DataFrame(review_data)
            
            # ファイル名を生成（タイムスタンプ付き）
            filename = os.path.join(output_dir, f"rakuten_{keyword}_reviews_{timestamp}.csv")
            
            # CSVファイルとして保存
            reviews_df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"レビュー情報を {filename} に保存しました。合計: {len(review_data)}件")
            
            return filename
        
        except Exception as e:
            print(f"レビュー情報の保存中にエラーが発生しました: {e}")
            return None

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