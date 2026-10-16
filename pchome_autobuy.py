#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import re
import json
import time
import sys
import random
import requests
import undetected_chromedriver as uc

from countdown import countdown_timer

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

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
    url = url.strip()
    pattern = r'(?<=prod/)(\w+-\w+)'
    try:
        found = re.findall(pattern, url)
        if found:
            return found[0]
        clean_id = re.search(r'([A-Za-z0-9]+-[A-Za-z0-9]+)', url)
        if clean_id:
            return clean_id.group(1)
        return url
    except Exception as e:
        print(e.__class__.__name__, ': 取得商品 ID 錯誤！')
        return url

def normalize_product_url(prod_input):
    prod_input = prod_input.strip()
    if prod_input.startswith("http://") or prod_input.startswith("https://"):
        return prod_input
    prod_id = get_product_id(prod_input)
    return f"https://24h.pchome.com.tw/prod/{prod_id}"

def get_product_status(product_id):
    product_id = get_product_id(product_id)
    api_url = f'https://ecapi.pchome.com.tw/ecshop/prodapi/v2/prod/button&id={product_id}'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
    try:
        resp = requests.get(api_url, headers=headers, timeout=3)
        status = json.loads(resp.text)[0]['ButtonType']
        return status
    except Exception:
        return 'Unknown'

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

def select_payment_method(allow_atm_fallback=True):
    """
    智能偵測並切換付款方式：
    1. 優先精確點擊選取「其他付款方式」➔「貨到付款 (COD)」。
    2. 若商品/訂單不支援貨到付款：
       - 若 allow_atm_fallback=True，自動選取「ATM 轉帳」秒搶單！
       - 嚴格檢查：若畫面依然選在「信用卡一次付清」（信用卡卡號欄位仍可見），代表未切換成功，絕對不放行送出！
    回傳 dict: {"success": bool, "method": str, "msg": str}
    """
    js_click_other = """
    function simulateRealClick(el) {
        if (!el) return false;
        try { el.scrollIntoView({ behavior: 'instant', block: 'center' }); } catch(e) {}
        var rect = el.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height / 2;
        var evtOpts = { bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy };
        el.dispatchEvent(new MouseEvent('mouseenter', evtOpts));
        el.dispatchEvent(new MouseEvent('mouseover', evtOpts));
        el.dispatchEvent(new MouseEvent('mousedown', evtOpts));
        el.dispatchEvent(new MouseEvent('mouseup', evtOpts));
        el.dispatchEvent(new MouseEvent('click', evtOpts));
        if (el.tagName === 'INPUT' && el.type === 'radio') {
            el.checked = true;
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        return true;
    }

    // 透過精確 XPath 找出真正代表「其他付款方式」的文字節點（排除包含全部內容的大容器）
    var xpath = "//*[text()[contains(., '其他付款方式')]]";
    var snap = document.evaluate(xpath, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
    var targetNode = null;
    for (var i = 0; i < snap.snapshotLength; i++) {
        var node = snap.snapshotItem(i);
        if (node.offsetParent !== null && node.textContent.trim().length <= 25) {
            targetNode = node;
            break;
        }
    }

    if (!targetNode && snap.snapshotLength > 0) {
        targetNode = snap.snapshotItem(0);
    }

    if (targetNode) {
        // 向上尋找最適合點擊的項目卡片或 label
        var clickTarget = targetNode.closest('label') || targetNode.closest('li') || targetNode.parentElement || targetNode;
        simulateRealClick(clickTarget);
        
        // 若裡面有 radio 或相鄰 radio
        var radio = clickTarget.querySelector('input[type="radio"]') || (clickTarget.parentElement ? clickTarget.parentElement.querySelector('input[type="radio"]') : null);
        if (radio) {
            simulateRealClick(radio);
        }
        return JSON.stringify({ status: 'CLICKED_OTHER' });
    }

    return JSON.stringify({ status: 'OTHER_NOT_FOUND', msg: '未在頁面上找到【其他付款方式】選項' });
    """

    js_select_sub = f"""
    var allowAtm = {str(allow_atm_fallback).lower()};
    function simulateRealClick(el) {{
        if (!el) return false;
        try {{ el.scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
        var rect = el.getBoundingClientRect();
        var cx = rect.left + rect.width / 2;
        var cy = rect.top + rect.height / 2;
        var evtOpts = {{ bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy }};
        el.dispatchEvent(new MouseEvent('mouseenter', evtOpts));
        el.dispatchEvent(new MouseEvent('mouseover', evtOpts));
        el.dispatchEvent(new MouseEvent('mousedown', evtOpts));
        el.dispatchEvent(new MouseEvent('mouseup', evtOpts));
        el.dispatchEvent(new MouseEvent('click', evtOpts));
        if (el.tagName === 'INPUT' && el.type === 'radio') {{
            el.checked = true;
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}
        return true;
    }}

    // 1. 檢查展開後的下拉選單 <select>
    var selects = document.querySelectorAll('select');
    for (var i = 0; i < selects.length; i++) {{
        var sel = selects[i];
        if (sel.offsetParent !== null) {{
            // 優先找貨到付款
            for (var j = 0; j < sel.options.length; j++) {{
                if (sel.options[j].text.indexOf('貨到付款') !== -1) {{
                    sel.selectedIndex = j;
                    sel.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return JSON.stringify({{ status: 'SELECTED', method: '貨到付款' }});
                }}
            }}
            // 若允許 ATM
            if (allowAtm) {{
                for (var j = 0; j < sel.options.length; j++) {{
                    if (sel.options[j].text.indexOf('ATM') !== -1) {{
                        sel.selectedIndex = j;
                        sel.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        sel.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return JSON.stringify({{ status: 'SELECTED', method: 'ATM 轉帳（商品不支援貨到付款，自動備選）' }});
                    }}
                }}
            }}
        }}
    }}

    // 2. 檢查展開後的單選子選項（依文字 XPath 尋找）
    var xpathCod = "//*[text()[contains(., '貨到付款')]]";
    var snapCod = document.evaluate(xpathCod, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
    for (var i = 0; i < snapCod.snapshotLength; i++) {{
        var node = snapCod.snapshotItem(i);
        if (node.offsetParent !== null && node.textContent.trim().length <= 15) {{
            var tgt = node.closest('label') || node.closest('li') || node.parentElement || node;
            simulateRealClick(tgt);
            return JSON.stringify({{ status: 'SELECTED', method: '貨到付款' }});
        }}
    }}

    // 3. 若無貨到付款，尋找獨立的 ATM 子選項
    if (allowAtm) {{
        var xpathAtm = "//*[text()[contains(., 'ATM')]]";
        var snapAtm = document.evaluate(xpathAtm, document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
        for (var i = 0; i < snapAtm.snapshotLength; i++) {{
            var node = snapAtm.snapshotItem(i);
            var txt = node.textContent.trim();
            // 排除描述字樣 "ATM、7-11 ibon"
            if (node.offsetParent !== null && txt.indexOf('7-11') === -1 && txt.length <= 15) {{
                var tgt = node.closest('label') || node.closest('li') || node.parentElement || node;
                simulateRealClick(tgt);
                return JSON.stringify({{ status: 'SELECTED', method: 'ATM 轉帳（商品不支援貨到付款，自動備選）' }});
            }}
        }}
    }}

    return JSON.stringify({{ status: 'NOT_FOUND', msg: '未在子選單中找到貨到付款或 ATM 選項' }});
    """

    try:
        raw_res1 = driver.execute_script(js_click_other)
        res1 = json.loads(raw_res1) if isinstance(raw_res1, str) else (raw_res1 or {})
        
        if res1.get('status') == 'CLICKED_OTHER':
            print("-> 已點擊【其他付款方式】，等待 0.6 秒展開子選單...")
            time.sleep(0.6)
            
            raw_res2 = driver.execute_script(js_select_sub)
            res2 = json.loads(raw_res2) if isinstance(raw_res2, str) else (raw_res2 or {})
            
            if res2.get('status') == 'SELECTED':
                return {"success": True, "method": res2.get('method', ''), "msg": "付款方式選取成功"}
            else:
                return {"success": False, "method": "", "msg": res2.get('msg', '未能選取貨到付款或 ATM')}
        else:
            return {"success": False, "method": "", "msg": res1.get('msg', '未找到其他付款方式項目')}
    except Exception as e:
        return {"success": False, "method": "", "msg": f"選取付款方式發生例外：{str(e)}"}

def select_cash_on_delivery():
    """相容舊函式呼叫"""
    res = select_payment_method(allow_atm_fallback=True)
    return res["success"]

def add_to_cart_flow(target_url_or_id):
    """
    開啟指定商品頁面，若有規格則隨機選取，並點擊加入購物車
    """
    target_url = normalize_product_url(target_url_or_id)
    print(f"-> 準備前往商品頁面: {target_url}")
    driver.get(target_url)

    # 若有規格選項，隨機選取一個可用規格
    select_random_specs()

    # 放入購物車
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

def checkout_flow(is_gui=False):
    """
    前往購物車進行結帳流程（Step 1 -> 自動選貨到付款/ATM -> Step 2 送出訂單）
    """
    print("-> 準備前往購物車結帳頁面...")
    driver.get("https://ecssl.pchome.com.tw/sys/cflow/fsindex/BigCar/BIGCAR/ItemList")

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

        # 智能選取付款方式（優先貨到付款，不支援時自動備選 ATM）
        pay_result = select_payment_method(allow_atm_fallback=True)

        # 嚴格驗證：檢查畫面是否依然選在信用卡（信用卡欄位依然顯眼可見）
        time.sleep(0.3)
        is_card_still_active = driver.execute_script("""
            var inputs = document.querySelectorAll('input');
            for (var i = 0; i < inputs.length; i++) {
                var p = inputs[i].placeholder || '';
                if (p.indexOf('信用卡') !== -1 && inputs[i].offsetParent !== null) {
                    return true;
                }
            }
            return false;
        """)

        if is_card_still_active:
            err_msg = "⚠️ 付款方式未能成功套用（畫面依然停留於信用卡輸入）！已暫停送出，請在瀏覽器中手動點擊付款方式！"
            print(f"-> {err_msg}")
            raise Exception(err_msg)

        if not pay_result["success"]:
            err_msg = f"⚠️ {pay_result['msg']}！請在已開啟的瀏覽器中手動選擇付款方式以完成結帳。"
            print(f"-> {err_msg}")
            raise Exception(err_msg)

        print(f"-> 付款方式確認完成：【{pay_result['method']}】")

        # 再次極速關閉可能出現的彈窗
        handle_confirm_dialog()

        # 等待按鈕可被點擊並送出訂單
        WebDriverWait(driver, 5).until(
            expected_conditions.element_to_be_clickable((By.XPATH, step2_xpath))
        )
        button_step2 = driver.find_element(By.XPATH, step2_xpath)
        driver.execute_script("arguments[0].click();", button_step2)
        print("-> 已點擊送出結帳按鈕，正在驗證訂單成立狀態...")

        # 真正驗證訂單是否成功成立（排除導覽列購買完成文字干擾）
        order_confirmed = False
        for _ in range(40):
            time.sleep(0.15)
            handle_confirm_dialog()
            page_text = driver.page_source
            curr_url = driver.current_url.lower()

            # 網址已跳出購物車並進入訂單完成頁面
            if any(k in curr_url for k in ["step3", "ordersuccess", "complete", "receipt"]) and "cart/p" not in curr_url:
                order_confirmed = True
                break
            # 頁面上出現訂單成立具體文字（非導覽列標題）
            if "訂單編號" in page_text or "感謝您的訂購" in page_text or "繳費代碼" in page_text or "虛擬帳號" in page_text:
                order_confirmed = True
                break
            # 仍被卡在信用卡驗證
            if "請輸入完整的信用卡號碼" in page_text:
                raise Exception("結帳未能送出：信用卡卡號為空！請手動在瀏覽器選取付款方式！")

        if order_confirmed:
            print("-> 🎉 訂單已成功成立！恭喜搶購完成！")
        else:
            print("-> 結帳步驟已送出，請在瀏覽器中確認訂單狀態。")

    except Exception as e:
        curr_url = driver.current_url if driver else ""
        if "login" in curr_url.lower():
            err_msg = "尚未登入 PChome 帳號！請先在開啟的瀏覽器中手動完成登入。"
        else:
            err_msg = str(e)
        print(f"-> [提醒/錯誤] {err_msg}")
        try:
            if driver:
                with open("error_cart.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print("-> 網頁結構已儲存為 error_cart.html。")
        except Exception:
            pass
        if not is_gui:
            input("請手動完成結帳，按 Enter 鍵結束程式...")
        raise Exception(err_msg)

    # 點擊額外提示視窗（如有）
    try:
        WebDriverWait(driver, 1).until(
            expected_conditions.element_to_be_clickable(
                (By.XPATH, "//a[@id='warning-timelimit_btn_confirm']"))
        )
        button = driver.find_element(By.XPATH, "//a[@id='warning-timelimit_btn_confirm']")
        driver.execute_script("arguments[0].click();", button)
    except Exception:
        pass

def main(is_gui=False):
    add_to_cart_flow(URL)
    checkout_flow(is_gui=is_gui)

def parse_prod_ids(prod_ids_input):
    if isinstance(prod_ids_input, str):
        raw_list = re.split(r'[;；,\n\r]+', prod_ids_input)
        return [item.strip() for item in raw_list if item.strip()]
    return [item.strip() for item in prod_ids_input if item.strip()]

def check_any_for_sale(prod_ids):
    """
    檢查清單中的商品開賣狀態。
    只要主要監控商品（第一筆）或任一商品轉為 ForSale 即視為開賣！
    """
    for pid in prod_ids:
        status = get_product_status(pid)
        if status == 'ForSale':
            return True, pid
    return False, None

def sniping_multiple_products(prod_ids_input, target_time_str="", status_callback=None, is_gui=False):
    """
    時間到達後，高頻監聽 API 確認開賣（ForSale），才依序加入購物車並結帳
    """
    global driver
    if driver is None:
        raise Exception("請先啟動瀏覽器並登入！")

    prod_ids = parse_prod_ids(prod_ids_input)
    if not prod_ids:
        raise Exception("請至少輸入一個有效的商品 ID！")

    # 1. 若有指定開賣時間，先進行倒數
    if target_time_str:
        countdown_timer(target_time_str, status_callback=status_callback)

    # 2. 時間已到：高頻輪詢確認開賣（ForSale）
    print("-> 時間已到！開始高頻 API 輪詢監聽開賣狀態...")
    curr_retry = 0
    max_retry = 999999
    wait_sec = 0.3

    while curr_retry <= max_retry:
        is_sale, forsale_id = check_any_for_sale(prod_ids)
        if not is_sale:
            curr_retry += 1
            msg = f"時間已到，等待商品正式開賣中 (嘗試第 {curr_retry} 次)..."
            if curr_retry % 5 == 1:
                print(f"-> {msg}")
            if status_callback:
                status_callback(msg)
            time.sleep(wait_sec)
        else:
            msg = f"🎉 偵測到商品【{forsale_id}】已確認開賣 (ForSale)！立即依序加車結帳！"
            print(f"-> {msg}")
            if status_callback:
                status_callback(msg)
            break

    # 3. 依序加入購物車
    total = len(prod_ids)
    for i, pid in enumerate(prod_ids, start=1):
        msg = f"正在加入第 ({i}/{total}) 個商品至購物車：{pid}"
        print(f"-> {msg}")
        if status_callback:
            status_callback(msg)
        add_to_cart_flow(pid)
        time.sleep(0.3)

    # 4. 前往快速結帳
    msg = "所有商品已成功加入購物車！正在前往快速結帳..."
    print(f"-> {msg}")
    if status_callback:
        status_callback(msg)

    checkout_flow(is_gui=is_gui)
    finish_msg = f"已成功將 {total} 項商品加入購物車並送出快速結帳！"
    print(f"-> {finish_msg}")
    if status_callback:
        status_callback(finish_msg)
    return finish_msg

def buy_multiple_products(prod_ids_input, status_callback=None, is_gui=False):
    """
    相容函式：若不帶時間直接調用 sniping_multiple_products
    """
    return sniping_multiple_products(prod_ids_input, target_time_str="", status_callback=status_callback, is_gui=is_gui)

def init_driver(chrome_path=""):
    global driver
    """
    設定 option 可讓 chrome 記住已登入帳戶，並設定視窗大小為 600*1024
    """
    # 若未指定 chrome_path，預設在專案目錄下建立專屬的 chrome_profile 資料夾，永久保存登入狀態
    if not chrome_path:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        chrome_path = os.path.join(base_dir, "chrome_profile")
        os.makedirs(chrome_path, exist_ok=True)
        print(f"-> 啟用專屬設定檔目錄（登入後自動記住，下次免登入）：{chrome_path}")

    options = webdriver.ChromeOptions()  
    options.add_argument("--window-size=600,1024")

    try:
        driver = uc.Chrome(options=options, user_data_dir=chrome_path)
    except Exception as e:
        import re
        match = re.search(r"Current browser version is (\d+)", str(e))
        if match:
            version_main = int(match.group(1))
            print(f"-> 偵測到您的 Chrome 版本為 {version_main}，自動修正啟動...")
            
            options2 = webdriver.ChromeOptions()
            options2.add_argument("--window-size=600,1024")
            driver = uc.Chrome(options=options2, user_data_dir=chrome_path, version_main=version_main)
        else:
            raise e

    try:
        driver.set_window_size(600, 1024)
    except Exception:
        pass

    driver.set_page_load_timeout(120)
    print("-> 正在開啟 PChome 首頁，請在瀏覽器中【手動完成登入】...")
    driver.get("https://24h.pchome.com.tw/")

def start_sniping(target_url, target_time_str="", status_callback=None, is_gui=False):
    global driver
    global URL
    if driver is None:
        print("請先啟動瀏覽器！")
        return

    # 若有指定開賣排程時間，先進行動態區間倒數
    if target_time_str:
        countdown_timer(target_time_str, status_callback=status_callback)
        
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
            main(is_gui=is_gui)
            break

if __name__ == "__main__":
    init_driver()
    print("\n👉 請在開啟的 Chrome 視窗中完成 PChome 帳號登入。")
    print("==================================================")
    print("【操作模式選擇】")
    print("1. 單品排程搶購（監控開賣時間後自動搶購）")
    print("2. 以 Prod ID 加入複數商品並快速結帳")
    print("==================================================")
    mode_choice = input("請輸入模式 (1 或 2，預設 1): ").strip()
    
    if mode_choice == "2":
        ids_input = input("請輸入商品 ID (多筆請以分號 ';' 分隔，例如 DGBH1H-A900XXXXX;DDADP3-A900YYYYY): ").strip()
        time_input = input("請輸入開賣時間 (格式 HH:MM:SS，直接按 Enter 則立即確認開賣並搶購): ").strip()
        if ids_input:
            sniping_multiple_products(ids_input, target_time_str=time_input)
        else:
            print("未輸入商品 ID，程式結束。")
    else:
        target = input(f"請輸入欲搶購的商品網址或 ID (直接 Enter 使用預設 {URL}): ").strip()
        if not target:
            target = URL
        time_input = input("請輸入開賣時間 (格式 HH:MM:SS，直接按 Enter 則立即開始監控): ").strip()
        input("👉 確認已登入並就緒，請按【Enter】開始監控開賣...")
        start_sniping(target, target_time_str=time_input)
