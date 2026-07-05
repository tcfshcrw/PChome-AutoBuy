import tkinter as tk
from tkinter import messagebox
import threading
import time
import json
from datetime import datetime

import pchome_autobuy

class AutoBuyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("PChome 搶購小幫手")
        self.root.geometry("400x350")
        self.root.resizable(False, False)

        self.config_path = "config.json"
        self.config_data = self.load_config()

        # UI 變數
        self.url_var = tk.StringVar(value=self.config_data.get("url", ""))
        self.time_var = tk.StringVar(value=self.config_data.get("time", "12:00:00"))
        self.status_var = tk.StringVar(value="尚未啟動")

        self.setup_ui()

    def load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_config(self):
        self.config_data["url"] = self.url_var.get().strip()
        self.config_data["time"] = self.time_var.get().strip()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print("無法儲存設定:", e)

    def setup_ui(self):
        # 標題
        tk.Label(self.root, text="PChome 搶購小幫手", font=("微軟正黑體", 16, "bold"), pady=10).pack()

        # 網址輸入
        tk.Label(self.root, text="商品網址:", font=("微軟正黑體", 10)).pack(anchor="w", padx=20)
        tk.Entry(self.root, textvariable=self.url_var, font=("微軟正黑體", 10), width=45).pack(padx=20, pady=5)

        # 時間輸入
        tk.Label(self.root, text="開賣時間 (HH:MM:SS):", font=("微軟正黑體", 10)).pack(anchor="w", padx=20, pady=(10, 0))
        tk.Entry(self.root, textvariable=self.time_var, font=("微軟正黑體", 12), width=20, justify="center").pack(pady=5)

        # 第一步：開啟瀏覽器
        self.btn_login = tk.Button(
            self.root, 
            text="第一步：開啟瀏覽器並登入", 
            font=("微軟正黑體", 10, "bold"), 
            bg="#f0ad4e", fg="white", 
            command=self.open_browser
        )
        self.btn_login.pack(fill="x", padx=40, pady=(15, 5))

        # 第二步：開始排程
        self.btn_start = tk.Button(
            self.root, 
            text="第二步：開始定時搶購", 
            font=("微軟正黑體", 10, "bold"), 
            bg="#5cb85c", fg="white", 
            command=self.start_schedule,
            state="disabled"
        )
        self.btn_start.pack(fill="x", padx=40, pady=5)

        # 狀態列
        tk.Label(self.root, textvariable=self.status_var, font=("微軟正黑體", 10), fg="blue").pack(pady=15)

    def open_browser(self):
        try:
            # 必須在背景執行以避免卡住 GUI
            def task():
                self.status_var.set("正在開啟瀏覽器... 請稍候")
                self.btn_login.config(state="disabled")
                try:
                    chrome_path = self.config_data.get("chrome_user_data_dir", "")
                    pchome_autobuy.init_driver(chrome_path)
                    self.status_var.set("瀏覽器已開啟！請在瀏覽器中手動登入")
                    # 開啟第二步按鈕
                    self.btn_start.config(state="normal")
                except Exception as e:
                    self.status_var.set("開啟瀏覽器失敗！")
                    messagebox.showerror("錯誤", f"開啟瀏覽器時發生錯誤:\n{str(e)}")
                    self.btn_login.config(state="normal")
            
            threading.Thread(target=task, daemon=True).start()
        except Exception as e:
            messagebox.showerror("錯誤", str(e))

    def start_schedule(self):
        target_time_str = self.time_var.get().strip()
        target_url = self.url_var.get().strip()
        
        if not target_url:
            messagebox.showwarning("警告", "請輸入商品網址！")
            return

        try:
            # 測試時間格式是否正確
            datetime.strptime(target_time_str, "%H:%M:%S")
            self.save_config() # 儲存設定
        except ValueError:
            messagebox.showwarning("警告", "時間格式錯誤！請輸入 HH:MM:SS\n例如：12:00:00")
            return

        self.btn_start.config(state="disabled")
        self.status_var.set(f"已排程！將於 {target_time_str} 開始監控")

        def schedule_task():
            while True:
                now = datetime.now()
                current_time_str = now.strftime("%H:%M:%S")
                
                # 如果還沒到時間，更新狀態並等待
                if current_time_str < target_time_str:
                    # 避免文字太頻繁閃爍，每秒更新一次
                    if now.microsecond < 100000:
                        self.status_var.set(f"倒數中... 目前時間 {current_time_str}")
                    time.sleep(0.1)
                else:
                    break
            
            self.status_var.set("時間到！開始狂刷 API 搶購...")
            try:
                pchome_autobuy.start_sniping(target_url)
                self.status_var.set("搶購程序結束。")
            except Exception as e:
                self.status_var.set("搶購發生錯誤！")
                messagebox.showerror("錯誤", f"搶購時發生錯誤:\n{str(e)}")
            finally:
                self.btn_start.config(state="normal")

        threading.Thread(target=schedule_task, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoBuyGUI(root)
    root.mainloop()
