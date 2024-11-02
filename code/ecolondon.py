import requests
import json
from datetime import datetime, timedelta
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import csv
import re

# 計算日期範圍
def calculate_dates(today_date_str):
    today = datetime.strptime(today_date_str, "%Y-%m-%d")
    start_date = datetime(2025, 1, 20)
    end_date = start_date + timedelta(days=(today - datetime(2024, 10, 21)).days)
    if today >= datetime(2024, 12, 20):
        end_date = datetime(2025, 3, 21)
        if today >= datetime(2025, 1, 20):
            start_date += timedelta(days=(today - datetime(2025, 1, 20)).days)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

# 初始化 Selenium 驅動
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--disable-software-rasterizer")
options.add_argument("--headless")
service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

# 重試機制
def retry(function, max_retries=3, delay=2):
    retries = 0
    while retries < max_retries:
        try:
            result = function()
            if result is not None:
                return result
        except (NoSuchElementException, TimeoutException, StaleElementReferenceException) as e:
            retries += 1
            print(f"重試第 {retries} 次，等待 {delay} 秒後重試... ({e})")
            time.sleep(delay)
    print("達到最大重試次數，操作失敗")
    return None

# 滾動到指定元素位置
def scroll_to_element(element):
    driver.execute_script("arguments[0].scrollIntoView(true);", element)

# 點擊元素並處理遮擋情況
def click_element(element):
    try:
        element.click()
        return True
    except ElementClickInterceptedException:
        print("元素被遮擋，嘗試滾動到元素位置")
        scroll_to_element(element)
        time.sleep(1)
        try:
            element.click()
            return True
        except ElementClickInterceptedException:
            print("使用 JavaScript 點擊元素")
            driver.execute_script("arguments[0].click();", element)
            return True
    except Exception as e:
        print(f"點擊元素失敗: {e}")
        return False

# 抓取航班資料
def scrape_flights(start_date_str, end_date_str):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    delta = timedelta(days=1)
    success_count = 0
    current_date = start_date

    while current_date <= end_date:
        print(f"正在抓取日期: {current_date.strftime('%Y-%m-%d')}")
        url = f"https://www.google.com/travel/flights/search?tfs=CBwQAholEgoyMDI1LTAxLTE5KAFqDAgCEggvbS8wZnRreHIHCAESA0xIUkABSAFwAYIBCwj___________8BmAEC&tfu=EgYIBRABGAA&hl=zh-TW&gl=TW"
        driver.get(url)

        try:
            # 點擊日期選擇器
            departure_date_picker = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, 'TP4Lpb'))
            )
            click_element(departure_date_picker)
            print("成功點擊出發日期選擇器")
        except Exception as e:
            print("無法找到出發日期選擇器", e)
            current_date += delta
            continue

        time.sleep(3)

        # 選擇日期
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
            current_date += delta
            continue

        # 點擊 Done 按鈕
        try:
            done_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//div[@class="WXaAwc"]//div//button'))
            )
            click_element(done_button)
            print("成功點擊 'Done' 按鈕")
        except Exception as e:
            print("無法找到 'Done' 按鈕", e)
            current_date += delta
            continue

        time.sleep(2)

        # 抓取航班資訊
        flight_links = WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.pIav2d"))
        )
        print(f"找到 {len(flight_links)} 個航班")

        output_directory = 'data'
        os.makedirs(output_directory, exist_ok=True)
        today_date = datetime.now().strftime("%m%d")

        with open(f'{output_directory}/busny_{today_date}.csv', 'a', newline='', encoding='utf-8-sig') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                "出發日期", "出發時間", "出發機場代號", 
                "抵達時間", "抵達機場代號", "航空公司", 
                "停靠站數量", "停留時間", "飛行時間", 
                "是否過夜", "機型", "航班代碼", "艙等", "價格"
            ])

            for index in range(len(flight_links)):
                try:
                    flight_links = driver.find_elements(By.CSS_SELECTOR, "li.pIav2d")
                    if index >= len(flight_links):
                        break

                    flight_element = flight_links[index]
                    flight_buttons = flight_element.find_elements(By.XPATH, ".//div[@class='vJccne  trZjtf']//div[@class='VfPpkd-dgl2Hf-ppHlrf-sM5MNb']")

                    if flight_buttons:
                        click_element(flight_buttons[0])
                        time.sleep(3)

                    try:
                        # 抓取航班細節
                        departure_info = flight_element.find_element(By.XPATH, ".//div[@class='PzDBM']/div[1]").text
                        arrival_info = flight_element.find_element(By.XPATH, ".//div[@class='PzDBM']/div[2]").text
                        flight_time = flight_element.find_element(By.XPATH, ".//div[@class='GVjYrb MhtlBb']").text
                        stops_info = flight_element.find_element(By.XPATH, ".//div[@class='GVjYrb UWkiv']").text
                        carrier_info = flight_element.find_element(By.XPATH, ".//div[@class='VfPpkd-StrnGf-rymPhb-ibnC6b']").text
                        aircraft_model = flight_element.find_element(By.XPATH, ".//div[@class='iFO0te']").text

                        # 提取航班資訊的各項細節
                        departure_time, departure_airport = departure_info.split('\n')
                        arrival_time, arrival_airport = arrival_info.split('\n')
                        flight_duration = flight_time.replace('Flight time ', '').strip()
                        stops = "Direct" if "Nonstop" in stops_info else stops_info.split('·')[0].strip()
                        layover_time = stops_info.split('·')[1].strip() if "·" in stops_info else "N/A"
                        overnight = "Yes" if "Overnight" in stops_info else "No"
                        flight_class = "Economy"  # 假設為經濟艙，或者根據情境調整
                        price = flight_element.find_element(By.XPATH, ".//div[@class='U3gSDe']").text.replace("From ", "").strip()

                        # 寫入 CSV
                        csv_writer.writerow([
                            current_date.strftime('%Y-%m-%d'), departure_time, departure_airport,
                            arrival_time, arrival_airport, carrier_info,
                            stops, layover_time, flight_duration,
                            overnight, aircraft_model, carrier_info, flight_class, price
                        ])

                        print(f"成功抓取航班：{departure_time} - {arrival_time} ({carrier_info})")
                        success_count += 1

                    except Exception as e:
                        print(f"抓取航班細節失敗: {e}")
                        continue

                except Exception as e:
                    print(f"處理航班元素時出錯: {e}")
                    continue

        current_date += delta
    print(f"抓取完成，共成功抓取 {success_count} 筆航班資料")
