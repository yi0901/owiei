import requests
import json
from datetime import datetime, timedelta
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import csv
import re

# Discord Webhook URL
#WEBHOOK_URL = "https://discord.com/api/webhooks/1295434884361228450/zwTbBwZK3hryiEqFiCa6HWGXzZtWHRldTizl4BUNyZcw_0IHb94kbmikoKwOeFObbGBk"

# 發送 Discord 通知的函數
#def send_discord_notification(message):
 #   data = {"content": message}
  #  response = requests.post(WEBHOOK_URL, data=json.dumps(data), headers={"Content-Type": "application/json"})
   # if response.status_code == 204:
    #    logging.info("Discord 通知發送成功")
    #else:
     #   logging.error(f"Failed to send Discord notification: {response.status_code}, {response.text}")

def calculate_dates(today_date_str):
    today = datetime.strptime(today_date_str, "%Y-%m-%d")
    start_date = datetime(2025, 1, 20)
    end_date = start_date + timedelta(days=(today - datetime(2024, 10, 21)).days)

    # 如果是 2024-12-20 及以後，結束日期固定為 2025-03-21
    if today >= datetime(2024, 12, 20):
        end_date = datetime(2025, 3, 21)
        # 2025-01-20 之後，起始日開始遞增
        if today >= datetime(2025, 1, 20):
            start_date += timedelta(days=(today - datetime(2025, 1, 20)).days)

    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

# 設置 Selenium 驅動
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--disable-software-rasterizer")
options.add_argument("--headless")
service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

def scrape_flights(start_date_str, end_date_str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    delta = timedelta(days=1)
    success_count = 0  # 總共抓取的航班數量

    # 迴圈遍歷每個日期
    current_date = start_date
    while current_date <= end_date:
    print(f"正在抓取日期: {current_date.strftime('%Y-%m-%d')}")
    url = "https://www.google.com/travel/flights/search?tfs=CBwQAholEgoyMDI1LTAxLTE5KAFqDAgCEggvbS8wZnRreHIHCAESA0pGS0ABSANwAYIBCwj___________8BmAEC&tfu=EgYIABABGAA&hl=zh-TW&gl=TW"
    driver.get(url)

    try:
        departure_date_picker = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CLASS_NAME, 'TP4Lpb'))
        )
        click_element(departure_date_picker)
        print("成功點擊出發日期選擇器")
    except Exception as e:
        print("無法找到出發日期選擇器", e)

    time.sleep(3)  # 增加等待時間以確保日曆加載完成

        # 選擇具體日期
        def select_date(xpath):
            specific_date = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            if specific_date:
                scroll_to_element(specific_date)
                click_element(specific_date)
                print(f"成功選擇出發日期 {current_date.strftime('%Y 年 %m 月 %d 日')}")
                return True
            return None

        xpaths = [
            f"//div[@class='WhDFk Io4vne' and @data-iso='{current_date.strftime('%Y-%m-%d')}']//div[@role='button']",
            f"//div[@class='WhDFk Io4vne Xu6rJc' and @data-iso='{current_date.strftime('%Y-%m-%d')}']//div[@role='button']",
            f"//div[@class='WhDFk Io4vne inxqCf' and @data-iso='{current_date.strftime('%Y-%m-%d')}']//div[@role='button']",
            f"//div[@class='WhDFk Io4vne OqiQxf' and @data-iso='{current_date.strftime('%Y-%m-%d')}']//div[@role='button']",
            f"//div[@class='p1BRgf KQqAEc' and @data-iso='{current_date.strftime('%Y-%m-%d')}']//div[@role='button']"
        ]

        date_selected = False
        for xpath in xpaths:
            if retry(lambda: select_date(xpath)):
                date_selected = True
                break

        if not date_selected:
            print(f"無法選擇出發日期 {current_date.strftime('%Y 年 %m 月 %d 日')}")
            current_date += delta  # 如果無法選擇，繼續到下一個日期
            continue  # 跳過當前迭代，進入下一個日期

        # 點擊 "Done" 按鈕
        try:
            done_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//div[@class="WXaAwc"]//div//button'))
            )
            click_element(done_button)
            print("成功點擊 'Done' 按鈕")
        except Exception as e:
            print("無法找到 'Done' 按鈕", e)
        
        
        time.sleep(5)

        # 獲取所有航班連結
        try:
            flight_links = WebDriverWait(driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.pIav2d"))
            )
            print(f"找到 {len(flight_links)} 個航班")
        except NoSuchElementException:
            print("找不到航班連結")
            current_date += delta
            continue

        # 確保 'data/' 目錄存在
        output_directory = 'data'
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)

        # 準備寫入 CSV 檔案
        today_date = datetime.now().strftime("%m%d")
        with open(f'{output_directory}/sydney_{today_date}.csv', 'a', newline='', encoding='utf-8-sig') as csv_file:
            csv_writer = csv.writer(csv_file)

            # 遍歷並點擊每個航班
            for index, flight_element in enumerate(flight_links):
                try:
                    driver.execute_script("arguments[0].scrollIntoView();", flight_element)  # 滾動到航班元素
                    flight_buttons = flight_element.find_elements(By.XPATH, ".//div[@class='vJccne  trZjtf']//div[@class='VfPpkd-dgl2Hf-ppHlrf-sM5MNb']//button")
                    flight_buttons[0].click()  # 點擊第一個按鈕
                    time.sleep(1)

                    # 抓取資料
                    # （此處省略原始程式碼中的抓取邏輯）

                    success_count += 1

                except (ElementClickInterceptedException, ElementNotInteractableException) as e:
                    print(f"無法點擊第 {index + 1} 個航班: {e}")
                    continue

        current_date += delta

    driver.quit()
    return success_count

# 根據當前日期計算動態起始日與結束日
today_str = datetime.now().strftime("%Y-%m-%d")
start_date_input, end_date_input = calculate_dates(today_str)

try:
    success_count = scrape_flights(start_date_input, end_date_input)
  #  send_discord_notification(f"共抓取 {success_count} 個航班，日期範圍: {start_date_input} 到 {end_date_input}")
except Exception as e:
 #   send_discord_notification(f"航班抓取失敗: {e}")
    success_count = 0

print(f"共抓取 {success_count} 個航班，日期範圍: {start_date_input} 到 {end_date_input}")

