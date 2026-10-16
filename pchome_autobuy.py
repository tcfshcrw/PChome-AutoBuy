#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import re
import json
import time
import random
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

def click_button(xpath, timeout=20):
    WebDriverWait(driver, timeout).until(
        expected_conditions.presence_of_element_located((By.XPATH, xpath))
    )
    elem = driver.find_element(By.XPATH, xpath)
    try:
        elem.click()
    except Exception:
        driver.execute_script("arguments[0].click();", elem)

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

def select_random_specs():
    """
    若商品有規格選項（顏色、尺寸等），隨機選擇一個可用的規格。
    若無規格選項則直接跳過，絕不誤點付款/運送說明等其他項目。
    """
    try:
        # 等待主要購買區按鈕載入，確保網頁主要區塊已就緒
        WebDriverWait(driver, 5).until(
            expected_conditions.presence_of_element_located((By.XPATH, xpaths['add_to_cart']))
        )

        # 真正的商品規格清單，PChome 24h 使用 normal_specItems
        # 且規格選項 li 帶有 c-detailCol__specItem--prodSpec
        spec_group_xpaths = [
            "//ul[@data-regression='normal_specItems']",
            "//ul[contains(@class, 'c-detailCol__specList') and .//li[contains(@class, 'c-detailCol__specItem--prodSpec')]]"
        ]

        spec_groups = []
        for sx in spec_group_xpaths:
            found = driver.find_elements(By.XPATH, sx)
            if found:
                # 確保裡面真的有 prodSpec 的按鈕，避免誤抓到付款/運送方式
                valid_groups = []
                for g in found:
                    spec_btns = g.find_elements(By.XPATH, ".//li[contains(@class, 'c-detailCol__specItem--prodSpec')]//button")
                    if spec_btns:
                        valid_groups.append(g)
                if valid_groups:
                    spec_groups = valid_groups
                    break

        if not spec_groups:
            print("-> 此商品無額外規格選項或已選定預設規格，直接進行購買流程。")
            return

        for group_idx, group in enumerate(spec_groups):
            buttons = group.find_elements(By.XPATH, ".//li[contains(@class, 'c-detailCol__specItem--prodSpec')]//button[not(@disabled)]")
            if not buttons:
                buttons = group.find_elements(By.XPATH, ".//button[not(@disabled)]")

            available_buttons = []
            for btn in buttons:
                btn_class = btn.get_attribute("class") or ""
                btn_inner = btn.get_attribute("innerHTML") or ""
                if "is-disabled" not in btn_class and "is-disabled" not in btn_inner:
                    available_buttons.append(btn)

            if available_buttons:
                chosen = random.choice(available_buttons)
                chosen_text = chosen.text.strip()
                if not chosen_text:
                    try:
                        chosen_text = chosen.find_element(By.XPATH, ".//span").text.strip()
                    except Exception:
                        chosen_text = "未命名規格"
                print(f"-> 偵測到規格選項（第 {group_idx + 1} 組），隨機選取規格：【{chosen_text}】")
                driver.execute_script("arguments[0].click();", chosen)
                time.sleep(0.5)
            else:
                print(f"-> 規格群組（第 {group_idx + 1} 組）暫無可選規格。")
    except Exception as e:
        print(f"-> 規格選取檢查略過：{e}")

def handle_confirm_dialog():
    """
    極速關閉或確認可能跳出的提示訊息對話框（如：訂單不受24小時到貨時間限制等）
    使用純 JS 在瀏覽器端毫秒級執行，不進行昂貴的 Python-Selenium 遠端遍歷
    """
    js_code = """
    try {
        var buttons = document.querySelectorAll('button, a, input[type="button"], input[type="submit"]');
        for (var i = 0; i < buttons.length; i++) {
            var b = buttons[i];
            if (b.offsetParent !== null) {
                var txt = (b.textContent || b.value || '').trim();
                if (txt === '確定' || txt === '我知道了' || txt === '同意') {
                    b.click();
                    return 'CONFIRMED';
                }
            }
        }
        var closeBtn = document.querySelector('button.close, [aria-label="Close"], [aria-label="關閉"]');
        if (closeBtn && closeBtn.offsetParent !== null) {
            closeBtn.click();
            return 'CLOSED';
        }
    } catch(e) {}
    return 'NONE';
    """
    try:
        res = driver.execute_script(js_code)
        if res in ('CONFIRMED', 'CLOSED'):
            print(f"-> 偵測到到貨限制/提示視窗，已自動處理關閉 ({res})。")
            return True
    except Exception:
        pass
    return False

def select_cash_on_delivery():
    """
    以原生 JavaScript 極速偵測並切換「其他付款方式」➔「貨到付款」
    耗時由數秒縮減至 0.1~0.2 秒以內
    """
    js_select_cod = """
    // 1. 檢查下拉選單 select
    var selects = document.querySelectorAll('select');
    for (var i = 0; i < selects.length; i++) {
        var opts = selects[i].options;
        for (var j = 0; j < opts.length; j++) {
            if (opts[j].text.indexOf('貨到付款') !== -1) {
                if (selects[i].selectedIndex !== j) {
                    selects[i].selectedIndex = j;
                    selects[i].dispatchEvent(new Event('change', { bubbles: true }));
                }
                return 'COD_SELECT_DONE';
            }
        }
    }

    // 2. 檢查單選框 radio 是否已有貨到付款
    var radios = document.querySelectorAll('input[type="radio"]');
    for (var i = 0; i < radios.length; i++) {
        var r = radios[i];
        var val = ((r.value || '') + (r.id || '') + (r.name || '')).toUpperCase();
        if (val.indexOf('COD') !== -1) {
            if (!r.checked) {
                r.click();
            }
            return 'COD_RADIO_DONE';
        }
    }

    // 3. 檢查文字包含「貨到付款」的可見元素
    var candidates = document.querySelectorAll('label, button, span, li, div');
    for (var i = 0; i < candidates.length; i++) {
        var el = candidates[i];
        if (el.children.length <= 2 && el.textContent.indexOf('貨到付款') !== -1 && el.offsetParent !== null) {
            el.click();
            return 'COD_CLICK_DONE';
        }
    }

    // 4. 若尚未找到貨到付款，尋找並展開「其他付款方式」
    for (var i = 0; i < candidates.length; i++) {
        var el = candidates[i];
        if (el.children.length <= 2 && el.textContent.indexOf('其他付款方式') !== -1 && el.offsetParent !== null) {
            el.click();
            return 'NEED_EXPAND_OTHER';
        }
    }

    return 'NOT_FOUND';
    """
    try:
        status = driver.execute_script(js_select_cod)
        if status in ('COD_SELECT_DONE', 'COD_RADIO_DONE', 'COD_CLICK_DONE'):
            print("-> 付款方式已確認為【貨到付款】。")
            return True
        elif status == 'NEED_EXPAND_OTHER':
            print("-> 點擊展開【其他付款方式】...")
            time.sleep(0.15)  # 極短等待子選單渲染
            status2 = driver.execute_script(js_select_cod)
            if status2 in ('COD_SELECT_DONE', 'COD_RADIO_DONE', 'COD_CLICK_DONE'):
                print("-> 成功切換付款方式為【貨到付款】！")
                return True
    except Exception as e:
        print(f"-> 快速付款檢查略過: {e}")
    return False

def main():
    print("-> 準備前往商品頁面...")
    driver.get(URL)

    """
    若有規格選項，隨機選取一個可用規格
    """
    select_random_specs()

    """
    放入購物車
    """
    print("-> 準備點擊放入購物車...")
    click_button(xpaths['add_to_cart'])
    
    # 智慧等待購物車數量更新（最多等 2 秒）
    cart_added = False
    for _ in range(5):
        time.sleep(0.3)
        try:
            badges = driver.find_elements(By.XPATH, "//div[@data-regression='header_cartNum']//div")
            if badges and badges[0].text.strip() not in ("", "0"):
                cart_added = True
                print(f"-> 商品成功加入購物車 (購物車數量: {badges[0].text.strip()})")
                break
        except Exception:
            pass
    if not cart_added:
        try:
            cart_btn = driver.find_element(By.XPATH, xpaths['add_to_cart'])
            driver.execute_script("arguments[0].click();", cart_btn)
            time.sleep(0.5)
        except Exception:
            pass

    """
    前往購物車
    """
    print("-> 準備前往購物車結帳頁面...")
    driver.get("https://ecssl.pchome.com.tw/sys/cflow/fsindex/BigCar/BIGCAR/ItemList")

    """
    前往結帳 (要使用 JS 的方式 execute_script 點擊)
    """
    print("-> 準備點擊前往結帳 (步驟 1/2)...")
    try:
        # 步驟一：購物車頁面的「結帳」按鈕
        step1_xpath = "//button[@data-regression='step1-checkout-btn']"
        WebDriverWait(driver, 20).until(
            expected_conditions.presence_of_element_located((By.XPATH, step1_xpath))
        )

        # 快速關閉可能已出現的彈窗
        handle_confirm_dialog()

        button_step1 = driver.find_element(By.XPATH, step1_xpath)
        driver.execute_script("arguments[0].click();", button_step1)
        print("-> 成功點擊前往結帳 (步驟 1/2)，正在前往結帳畫面...")

        # 點擊步驟一後，高頻監聽彈窗或步驟二出現（0.1 秒極速輪詢）
        step2_xpath = "//button[@data-regression='step2-checkout-btn']"
        for _ in range(40):  # 最多等 4 秒
            handle_confirm_dialog()
            if driver.find_elements(By.XPATH, step2_xpath):
                break
            time.sleep(0.1)

        WebDriverWait(driver, 10).until(
            expected_conditions.presence_of_element_located((By.XPATH, step2_xpath))
        )
        print("-> 成功進入結帳畫面 (步驟 2/2)...")

        # 毫秒級執行：自動選取「其他付款方式」->「貨到付款」
        select_cash_on_delivery()

        # 再次極速關閉可能出現的彈窗
        handle_confirm_dialog()

        # 等待按鈕可被點擊並送出訂單
        WebDriverWait(driver, 5).until(
            expected_conditions.element_to_be_clickable((By.XPATH, step2_xpath))
        )
        button_step2 = driver.find_element(By.XPATH, step2_xpath)
        driver.execute_script("arguments[0].click();", button_step2)
        print("-> 成功點擊最後送出結帳按鈕！")
        
    except Exception as e:
        curr_url = driver.current_url
        if "login" in curr_url.lower():
            print("-> [提醒] 尚未登入 PChome 帳號！請在開啟的瀏覽器中完成登入後手動結帳。")
        else:
            print("-> [錯誤] 找不到結帳按鈕！正在儲存目前網頁結構以供分析...")
        with open("error_cart.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("-> 網頁結構已儲存為 error_cart.html。您可以手動接手後續的結帳動作！")
        # 暫停讓使用者接手
        input("請手動完成結帳，按 Enter 鍵結束程式...")
        return
        
    except Exception as e:
        curr_url = driver.current_url
        if "login" in curr_url.lower():
            print("-> [提醒] 尚未登入 PChome 帳號！請在開啟的瀏覽器中完成登入後手動結帳。")
        else:
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
    設定 option 可讓 chrome 記住已登入帳戶，並設定視窗大小為 600*1024
    """
    options = webdriver.ChromeOptions()  
    options.add_argument("--window-size=600,1024")
    if chrome_path:
        options.add_argument(f"--user-data-dir={chrome_path}")  

    try:
        driver = uc.Chrome(options=options)
    except Exception as e:
        import re
        match = re.search(r"Current browser version is (\d+)", str(e))
        if match:
            version_main = int(match.group(1))
            print(f"-> 偵測到您的 Chrome 版本為 {version_main}，自動修正啟動...")
            
            options2 = webdriver.ChromeOptions()
            options2.add_argument("--window-size=600,1024")
            if chrome_path:
                options2.add_argument(f"--user-data-dir={chrome_path}")
            
            driver = uc.Chrome(options=options2, version_main=version_main)
        else:
            raise e

    try:
        driver.set_window_size(600, 1024)
    except Exception:
        pass

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
