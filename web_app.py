import os
import sys
import time
import json
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import logging

import pchome_autobuy

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
    "target_url": ""
}

def load_config():
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(url, time_str):
    config_data = load_config()
    config_data["url"] = url
    config_data["time"] = time_str
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print("無法儲存設定:", e)

config = load_config()
app_state["target_url"] = config.get("url", "")
app_state["target_time"] = config.get("time", "12:00:00")

@app.route('/')
def index():
    return render_template('index.html', url=app_state["target_url"], time=app_state["target_time"])

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
        return jsonify({"success": False, "message": "已經在排程中了"})

    data = request.json
    target_url = data.get("url", "").strip()
    target_time_str = data.get("time", "").strip()
    
    if not target_url:
        return jsonify({"success": False, "message": "請輸入商品網址"})
    
    try:
        datetime.strptime(target_time_str, "%H:%M:%S")
    except ValueError:
        return jsonify({"success": False, "message": "時間格式錯誤！請輸入 HH:MM:SS"})

    save_config(target_url, target_time_str)
    app_state["target_url"] = target_url
    app_state["target_time"] = target_time_str
    app_state["is_scheduling"] = True

    def schedule_task():
        app_state["status"] = f"已排程！將於 {target_time_str} 開始監控"
        while True:
            now = datetime.now()
            current_time_str = now.strftime("%H:%M:%S")
            if current_time_str < target_time_str:
                app_state["status"] = f"倒數中，目前時間 {current_time_str}"
                time.sleep(0.5)
            else:
                break
        
        app_state["status"] = "時間到！開始狂刷 API 搶購"
        try:
            pchome_autobuy.start_sniping(target_url)
            app_state["status"] = "搶購程序結束。"
        except Exception as e:
            app_state["status"] = f"搶購發生錯誤：{str(e)}"
        finally:
            app_state["is_scheduling"] = False

    threading.Thread(target=schedule_task, daemon=True).start()
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
