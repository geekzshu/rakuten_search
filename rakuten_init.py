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

class RakutenInit:
    def __init__(self, application_id):
        self.application_id = application_id
        self.driver = None
        self.wait = None

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
            try:
                # 代替方法を試す - 直接Chromeドライバーを使用
                self.driver = webdriver.Chrome(options=chrome_options)
                print("代替方法でChromeドライバーが初期化されました")
            except Exception as e2:
                print(f"Chromeドライバーの初期化に完全に失敗しました: {e2}")
                self.driver = None
                raise Exception("Seleniumドライバーの初期化に失敗しました")