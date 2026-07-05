#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import re
import json
import time
import requests
import undetected_chromedriver as uc

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By

driver = None

"""
匯入欲搶購的連結及其他設定（現在由 GUI 的 config.json 管理）
"""
# 移除從 settings 引入的寫法
URL = ""

def login():
    WebDriverWait(driver, 2).until(
        expected_conditions.presence_of_element_located((By.ID, 'loginAcc'))
    )
    elem = driver.find_element(By.ID, 'loginAcc')
    elem.clear()
    elem.send_keys(ACC)
    elem = driver.find_element(By.ID, 'loginPwd')
    elem.clear()
    elem.send_keys(PWD)
    WebDriverWait(driver, 20).until(
        expected_conditions.element_to_be_clickable((By.ID, "btnLogin"))
    )
    driver.find_element(By.ID, 'btnLogin').click()
    print('成功登入')

def input_info(xpath, info):  # info = 個資
    WebDriverWait(driver, 1).until(
        expected_conditions.element_to_be_clickable(
            (By.XPATH, xpath))
    )
    elem = driver.find_element(By.XPATH, xpath)
    elem.clear()
    elem.send_keys(info)

def click_button(xpath):
    WebDriverWait(driver, 20).until(
        expected_conditions.element_to_be_clickable(
            (By.XPATH, xpath))
    )
    driver.find_element(By.XPATH, xpath).click()

def input_flow():
    """
    填入個資，若無法填入則直接填入信用卡背面安全碼 3 碼 (multi_CVV2Num)
    """
    try:
        input_info(xpaths['BuyerSSN'], BuyerSSN)
        input_info(xpaths['BirthYear'], BirthYear)
        input_info(xpaths['BirthMonth'], BirthMonth)
        input_info(xpaths['BirthDay'], BirthDay)
    except:
        print("Birth's info already filled in!")
    finally:
        input_info(xpaths['multi_CVV2Num'], multi_CVV2Num)

def get_product_id(url):
    pattern = r'(?<=prod/)(\w+-\w+)'
    try:
        product_id = re.findall(pattern, url)[0]
        print(product_id)
        return product_id
    except Exception as e:
        print(e.__class__.__name__, ': 取得商品 ID 錯誤！')

def get_product_status(product_id):
    api_url = f'https://ecapi.pchome.com.tw/ecshop/prodapi/v2/prod/button&id={product_id}'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
    resp = requests.get(api_url, headers=headers)
    status = json.loads(resp.text)[0]['ButtonType']
    return status

"""
集中管理需要的 xpath
"""
xpaths = {
    'add_to_cart': r"//button[@data-regression='product_button_addToCart']",
    'check_agree': r"//input[@name='chk_agree']",
    'BuyerSSN': r"//input[@id='BuyerSSN']",
    'BirthYear': r"//input[@name='BirthYear']",
    'BirthMonth': r"//input[@name='BirthMonth']",
    'BirthDay': r"//input[@name='BirthDay']",
    'multi_CVV2Num': r"//input[@name='multi_CVV2Num']"
    # 'pay_once': "//li[@class=CC]/a[@class='ui-btn']",
    # 'pay_line': "//li[@class=LIP]/a[@class='ui-btn line_pay']", 
    # 'submit': "//a[@id='btnSubmit']",
    # 'warning_msg': "//a[@id='warning-timelimit_btn_confirm']",  # 之後可能會有變動
}

def main():
    print("-> 準備前往商品頁面...")
    driver.get(URL)

    """
    放入購物車
    """
    print("-> 準備點擊放入購物車...")
    click_button(xpaths['add_to_cart'])
    
    # 點擊後等待 2 秒，讓網頁有時間將商品真正加入伺服器購物車，避免跳轉太快導致購物車是空的
    time.sleep(2)

    """
    前往購物車
    """
    print("-> 準備前往購物車結帳頁面...")
    driver.get("https://ecssl.pchome.com.tw/sys/cflow/fsindex/BigCar/BIGCAR/ItemList")

    """
    登入帳戶（若有使用 CHROME_PATH 記住登入資訊，第二次執行時可註解掉）
    """
    # try:
    #     print("-> 準備嘗試登入帳戶...")
    #     login()
    # except:
    #     print('Already Logged in!')

    """
    前往結帳 (要使用 JS 的方式 execute_script 點擊)
    """
    print("-> 準備點擊前往結帳 (步驟 1/2)...")
    try:
        # 步驟一：購物車頁面的「結帳」按鈕
        step1_xpath = "//button[@data-regression='step1-checkout-btn']"
        WebDriverWait(driver, 20).until(
            expected_conditions.element_to_be_clickable((By.XPATH, step1_xpath))
        )
        button_step1 = driver.find_element(By.XPATH, step1_xpath)
        driver.execute_script("arguments[0].click();", button_step1)
        print("-> 成功進入結帳畫面，準備送出訂單 (步驟 2/2)...")
        
        # 步驟二：結帳頁面的「確認送出」按鈕
        step2_xpath = "//button[@data-regression='step2-checkout-btn']"
        WebDriverWait(driver, 20).until(
            expected_conditions.element_to_be_clickable((By.XPATH, step2_xpath))
        )
        button_step2 = driver.find_element(By.XPATH, step2_xpath)
        driver.execute_script("arguments[0].click();", button_step2)
        print("-> 成功點擊最後送出結帳按鈕！")
        
    except Exception as e:
        print("-> [錯誤] 找不到結帳按鈕！正在儲存目前網頁結構以供分析...")
        with open("error_cart.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("-> 網頁結構已儲存為 error_cart.html。您可以手動接手後續的結帳動作！")
        # 暫停讓使用者接手
        input("請手動完成結帳，按 Enter 鍵結束程式...")
        return

    """
    LINE Pay 付款
    """
    # WebDriverWait(driver, 20).until(
    #     expected_conditions.element_to_be_clickable(
    #         (By.XPATH, "//li[@class='LIP']/a[@class='ui-btn line_pay']"))
    # )
    # button = driver.find_element(By.XPATH, 
    #     "//li[@class='LIP']/a[@class='ui-btn line_pay']")
    # driver.execute_script("arguments[0].click();", button)

    """
    點擊提示訊息確定 (有些商品可能不需要)
    """
    try:
        WebDriverWait(driver, 1).until(
            expected_conditions.element_to_be_clickable(
                (By.XPATH, "//a[@id='warning-timelimit_btn_confirm']"))
        )
        button = driver.find_element(By.XPATH, "//a[@id='warning-timelimit_btn_confirm']")
        driver.execute_script("arguments[0].click();", button)
    except:
        print('Warning message passed!')

    """
    填入個資 (新版 PChome 結帳頁面已移除舊有欄位，故先註解)
    """
    # input_flow()

    """
    勾選同意 (新版 PChome 已整合，故先註解)
    """
    # click_button(xpaths['check_agree'])

    """
    送出訂單 (新版 PChome 已在前面一併點擊 step2-checkout-btn，故先註解)
    """
    # WebDriverWait(driver, 20).until(
    #     expected_conditions.element_to_be_clickable(
    #         (By.XPATH, "//a[@id='btnSubmit']"))
    # )
    # button = driver.find_element(By.XPATH, "//a[@id='btnSubmit']")
    # driver.execute_script("arguments[0].click();", button)


def init_driver(chrome_path=""):
    global driver
    """
    設定 option 可讓 chrome 記住已登入帳戶
    """
    options = webdriver.ChromeOptions()  
    if chrome_path:
        options.add_argument(f"--user-data-dir={chrome_path}")  

    driver = uc.Chrome(options=options)
    driver.set_page_load_timeout(120)
    print("-> 正在開啟 PChome 首頁，請在瀏覽器中【手動完成登入】...")
    driver.get("https://24h.pchome.com.tw/")

def start_sniping(target_url):
    global driver
    global URL
    if driver is None:
        print("請先啟動瀏覽器！")
        return
        
    """
    抓取商品開賣資訊，並嘗試搶購
    """
    curr_retry = 0
    max_retry = 999999   # 讓它無限重試直到開賣
    wait_sec = 0.5       # 縮短檢查間隔為 0.5 秒，提高搶到的機率

    print(f"-> 開始監控商品開賣狀態: {target_url}")
    product_id = get_product_id(target_url)
    
    while curr_retry <= max_retry:  
        status = get_product_status(product_id)
        if status != 'ForSale':
            print('商品尚未開賣！')
            curr_retry += 1
            time.sleep(wait_sec)
        else:
            print('商品已開賣！')
            URL = target_url  # 覆蓋全域的 URL 以防 main() 吃到舊設定
            main()
            break

if __name__ == "__main__":
    init_driver()
    input("👉 登入完成後，請回到這裡按下【Enter】鍵，程式就會開始自動監控商品並搶購...")
    start_sniping(URL)
