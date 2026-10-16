#!/usr/bin/python
# -*- coding: UTF-8 -*-

import sys
import time
from datetime import datetime, timedelta

# 避免 Windows CMD / CP950 編碼輸出問題
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def parse_target_time(target):
    """
    將輸入的 target 轉換為目標 datetime 物件：
    - 支援整數/浮點數（視為倒數秒數）
    - 支援 datetime 物件
    - 支援 'HH:MM:SS' 或 'HH:MM'（若已過則自動推算為隔天跨日）
    - 支援 'YYYY-MM-DD HH:MM:SS'
    """
    if isinstance(target, (int, float)):
        return datetime.now() + timedelta(seconds=target)

    if isinstance(target, datetime):
        return target

    if not isinstance(target, str):
        raise ValueError(f"不支援的目標時間格式：{target}")

    target_str = target.strip()

    # 嘗試完整日期時間格式
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(target_str, fmt)
        except ValueError:
            pass

    # 嘗試 HH:MM:SS 或 HH:MM
    parts = target_str.split(":")
    if len(parts) in (2, 3):
        try:
            h = int(parts[0])
            m = int(parts[1])
            s = int(parts[2]) if len(parts) == 3 else 0
            now = datetime.now()
            target_dt = now.replace(hour=h, minute=m, second=s, microsecond=0)
            # 若目標時間比當前時間早，自動視為隔天跨日排程
            if target_dt <= now:
                target_dt += timedelta(days=1)
            return target_dt
        except ValueError:
            pass

    raise ValueError(f"無法解析的時間格式：'{target_str}'，請輸入 HH:MM:SS、YYYY-MM-DD HH:MM:SS 或純秒數")

def format_remaining_time(seconds):
    """
    將剩餘秒數格式化為清晰可讀的字串
    """
    total_sec = max(0, int(round(seconds)))
    hrs = total_sec // 3600
    mins = (total_sec % 3600) // 60
    secs = total_sec % 60

    if hrs > 0:
        return f"{hrs} 小時 {mins:02d} 分 {secs:02d} 秒"
    elif mins > 0:
        return f"{mins} 分 {secs:02d} 秒"
    else:
        return f"{secs} 秒"

def countdown_timer(target, status_callback=None, stop_event=None):
    """
    在 CMD 視窗顯示時間倒數：
    - 10 分鐘以上 (> 600s)：每 60 秒列印一次
    - 1 分鐘到 10 分鐘 (60s ~ 600s)：每 30 秒列印一次
    - 1 分鐘內 (< 60s)：每 1 秒列印一次
    
    :param target: 目標時間（字串 'HH:MM:SS'、秒數或 datetime）
    :param status_callback: 狀態回呼函式 callback(msg_str)
    :param stop_event: threading.Event()，若設定則可用於中斷倒數
    :return: True 表示順利倒數完成；False 表示被 stop_event 中斷
    """
    target_dt = parse_target_time(target)
    target_str = target_dt.strftime("%Y-%m-%d %H:%M:%S")

    start_now = datetime.now()
    initial_rem = (target_dt - start_now).total_seconds()

    if initial_rem <= 0:
        finish_msg = f"[{start_now.strftime('%H:%M:%S')}] [時間到] 目標時間 {target_str} 已到達，無需倒數。"
        print(f"-> {finish_msg}")
        if status_callback:
            status_callback(finish_msg)
        return True

    init_info = f"-> [倒數啟動] 開賣目標時間：{target_str}，距離現在還有 {format_remaining_time(initial_rem)}，開始倒數..."
    print(init_info)
    if status_callback:
        status_callback(init_info)

    last_log_time = 0.0
    last_tier = None  # 用於偵測何時跨入下一個區間 (3: >10m, 2: 1-10m, 1: <=1m)

    while True:
        if stop_event and stop_event.is_set():
            abort_msg = "[倒數已取消] 倒數排程已被手動停止。"
            print(f"-> {abort_msg}")
            if status_callback:
                status_callback(abort_msg)
            return False

        now = datetime.now()
        rem = (target_dt - now).total_seconds()

        # 時間到達
        if rem <= 0:
            finish_msg = f"[{now.strftime('%H:%M:%S')}] [時間到] 倒數結束，立即執行任務！"
            print(f"-> {finish_msg}")
            if status_callback:
                status_callback(finish_msg)
            return True

        # 判定目前區間與列印間隔
        if rem > 600:
            current_tier = 3
            interval = 60.0
        elif rem > 60:
            current_tier = 2
            interval = 30.0
        else:
            current_tier = 1
            interval = 1.0

        current_timestamp = time.time()
        
        # 判斷是否需要列印 log：
        # 1. 跨入更密集的新區間（例如從 >10分 進入 1-10分，或 1-10分 進入 1分內）
        # 2. 距離上次列印時間已達 interval
        should_log = False
        if last_tier is not None and current_tier < last_tier:
            should_log = True
        elif (current_timestamp - last_log_time) >= (interval - 0.05):
            should_log = True

        if should_log:
            rem_text = format_remaining_time(rem)
            now_str = now.strftime('%H:%M:%S')
            log_msg = f"[{now_str}] [倒數中] 距離目標 {target_dt.strftime('%H:%M:%S')} 剩餘 {rem_text} (約 {int(rem)} 秒)"
            print(f"-> {log_msg}")
            if status_callback:
                status_callback(log_msg)
            last_log_time = current_timestamp
            last_tier = current_tier

        # 細粒度睡眠 0.1 秒，確保能快速響應時間與 stop_event
        time.sleep(0.1)

if __name__ == "__main__":
    print("=" * 60)
    print("【CMD 視窗時間倒數工具】")
    print("規則：10分鐘以上每分鐘倒數一次 / 1分到10分每30秒一次 / 1分內每秒倒數")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        user_input = sys.argv[1].strip()
    else:
        user_input = input("請輸入倒數目標時間 (HH:MM:SS 或秒數，例如 12:00:00 或 65): ").strip()
    
    if not user_input:
        print("未輸入時間，程式結束。")
        sys.exit(0)

    try:
        if user_input.isdigit():
            user_input = int(user_input)
        countdown_timer(user_input)
    except Exception as e:
        print(f"發生錯誤：{e}")
