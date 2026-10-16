import os
import sys
import time
import json
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import logging

import pchome_autobuy
from countdown import countdown_timer

app = Flask(__name__)
# 關閉 Flask 預設的日誌輸出以免干擾 cmd 畫面
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

config_path = "config.json"
app_state = {
    "status": "尚未啟動",
    "is_browser_open": False,
    "is_scheduling": False,
    "target_time": "12:00:00",
    "target_url": "",
    "multi_prod_ids": "",
    "multi_time": "12:00:00",
    "mode": "multi"
}

def load_config():
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(url=None, time_str=None, multi_prod_ids=None, multi_time=None, mode=None):
    config_data = load_config()
    if url is not None:
        config_data["url"] = url
    if time_str is not None:
        config_data["time"] = time_str
    if multi_prod_ids is not None:
        config_data["multi_prod_ids"] = multi_prod_ids
    if multi_time is not None:
        config_data["multi_time"] = multi_time
    if mode is not None:
        config_data["mode"] = mode
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print("無法儲存設定:", e)

config = load_config()
app_state["target_url"] = config.get("url", "")
app_state["target_time"] = config.get("time", "12:00:00")
app_state["multi_prod_ids"] = config.get("multi_prod_ids", "")
app_state["multi_time"] = config.get("multi_time", "12:00:00")
app_state["mode"] = config.get("mode", "multi")

@app.route('/')
def index():
    return render_template(
        'index.html',
        url=app_state["target_url"],
        time=app_state["target_time"],
        multi_prod_ids=app_state["multi_prod_ids"],
        multi_time=app_state["multi_time"],
        mode=app_state["mode"]
    )

@app.route('/api/open_browser', methods=['POST'])
def open_browser():
    if app_state["is_browser_open"]:
        return jsonify({"success": False, "message": "瀏覽器已經開啟了"})

    def task():
        app_state["status"] = "正在開啟瀏覽器，請稍候"
        try:
            chrome_path = load_config().get("chrome_user_data_dir", "")
            pchome_autobuy.init_driver(chrome_path)
            app_state["status"] = "瀏覽器已開啟！請在瀏覽器中手動登入"
            app_state["is_browser_open"] = True
        except Exception as e:
            app_state["status"] = f"開啟瀏覽器失敗：{str(e)}"
    
    threading.Thread(target=task, daemon=True).start()
    return jsonify({"success": True})

@app.route('/api/start_schedule', methods=['POST'])
def start_schedule():
    if not app_state["is_browser_open"]:
        return jsonify({"success": False, "message": "請先開啟瀏覽器並登入"})
    if app_state["is_scheduling"]:
        return jsonify({"success": False, "message": "目前有其他搶購或結帳任務正在進行中"})

    data = request.json or {}
    target_url = data.get("url", "").strip()
    target_time_str = data.get("time", "").strip()
    
    if not target_url:
        return jsonify({"success": False, "message": "請輸入商品網址或商品 ID"})
    
    try:
        datetime.strptime(target_time_str, "%H:%M:%S")
    except ValueError:
        return jsonify({"success": False, "message": "時間格式錯誤！請輸入 HH:MM:SS"})

    save_config(url=target_url, time_str=target_time_str, mode="schedule")
    app_state["target_url"] = target_url
    app_state["target_time"] = target_time_str
    app_state["mode"] = "schedule"
    app_state["is_scheduling"] = True

    def schedule_task():
        def update_status(msg):
            app_state["status"] = msg

        try:
            countdown_timer(target_time_str, status_callback=update_status)
            app_state["status"] = "時間到！開始狂刷 API 搶購"
            pchome_autobuy.start_sniping(target_url, is_gui=True)
            app_state["status"] = "搶購結帳程序已完成！"
        except Exception as e:
            app_state["status"] = f"搶購發生錯誤：{str(e)}"
        finally:
            app_state["is_scheduling"] = False

    threading.Thread(target=schedule_task, daemon=True).start()
    return jsonify({"success": True})

@app.route('/api/start_multi_checkout', methods=['POST'])
def start_multi_checkout():
    if not app_state["is_browser_open"]:
        return jsonify({"success": False, "message": "請先開啟瀏覽器並登入"})
    if app_state["is_scheduling"]:
        return jsonify({"success": False, "message": "目前有其他搶購或結帳任務正在進行中"})

    data = request.json or {}
    prod_ids = data.get("prod_ids", "").strip()
    multi_time_str = data.get("time", "").strip()
    
    if not prod_ids:
        return jsonify({"success": False, "message": "請輸入商品 ID（多筆請以分號 ';' 分隔）"})

    if multi_time_str:
        try:
            datetime.strptime(multi_time_str, "%H:%M:%S")
        except ValueError:
            return jsonify({"success": False, "message": "時間格式錯誤！請輸入 HH:MM:SS 或留空立即購買"})

    save_config(multi_prod_ids=prod_ids, multi_time=multi_time_str, mode="multi")
    app_state["multi_prod_ids"] = prod_ids
    app_state["multi_time"] = multi_time_str
    app_state["mode"] = "multi"
    app_state["is_scheduling"] = True

    def multi_task():
        def update_status(msg):
            app_state["status"] = msg

        try:
            pchome_autobuy.sniping_multiple_products(
                prod_ids,
                target_time_str=multi_time_str,
                status_callback=update_status,
                is_gui=True
            )
            app_state["status"] = "複數商品已確認開賣並全數加車完成結帳！"
        except Exception as e:
            app_state["status"] = f"搶購結帳發生錯誤：{str(e)}"
        finally:
            app_state["is_scheduling"] = False

    threading.Thread(target=multi_task, daemon=True).start()
    return jsonify({"success": True})

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "status": app_state["status"],
        "is_browser_open": app_state["is_browser_open"],
        "is_scheduling": app_state["is_scheduling"]
    })

@app.route('/api/close', methods=['POST'])
def close_app():
    def task():
        try:
            if pchome_autobuy.driver:
                pchome_autobuy.driver.quit()
        except Exception:
            pass
        time.sleep(0.5)
        os._exit(0)
    
    threading.Thread(target=task, daemon=True).start()
    return jsonify({"success": True, "message": "程式即將關閉"})

if __name__ == '__main__':
    print("網頁伺服器已啟動，請在瀏覽器中開啟 http://127.0.0.1:5000")
    print("按下 Ctrl+C 或是點擊網頁上的關閉按鈕來結束程式。")
    import webbrowser
    threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:5000')).start()
    app.run(host='127.0.0.1', port=5000, debug=False)
