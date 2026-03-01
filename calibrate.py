#!/usr/bin/env python3
"""
キャリブレーションツール
リアルタイムで「プレイ中」「デス」両状態を表示
"""
import sys
import time
import numpy as np
import yaml
from mss import mss
from datetime import datetime

if sys.platform == 'win32':
    import win32gui
else:
    win32gui = None

OW_WINDOW_KEYWORDS = ['overwatch', 'ow2']


def is_ow_foreground():
    if win32gui is None:
        return True
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd).lower()
        return any(kw in title for kw in OW_WINDOW_KEYWORDS)
    except Exception:
        return False


def check_icon_state(img_bgr, white_threshold=180, white_ratio_trigger=0.25):
    edge = 10
    left_bgr  = img_bgr[:, :edge, :].mean(axis=(0, 1))
    right_bgr = img_bgr[:, -edge:, :].mean(axis=(0, 1))

    def is_cyan(bgr):
        b, g, r = bgr
        return g > 100 and b > 140 and b > r + 60

    left_cyan  = is_cyan(left_bgr)
    right_cyan = is_cyan(right_bgr)
    cyan_ok    = left_cyan and right_cyan

    white_mask  = np.all(img_bgr > white_threshold, axis=2)
    white_ratio = white_mask.mean()
    is_death    = white_ratio >= white_ratio_trigger

    return cyan_ok, is_death, white_ratio, left_cyan, right_cyan


def load_config(config_path='config.yaml'):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def live_monitor(config):
    print("=== リアルタイムモニター (Ctrl+C で終了) ===")
    print("凡例: [OW=フォーカス] [水色=フレーム] [白=ドクロ] [状態]\n")

    watch = config['monitor']['watch_region']
    wt    = config['monitor'].get('white_threshold', 180)
    wr    = config['monitor'].get('white_ratio_trigger', 0.25)

    monitor = {'left': watch['x'], 'top': watch['y'], 'width': watch['width'], 'height': watch['height']}

    with mss() as sct:
        try:
            while True:
                ow_focus = is_ow_foreground()
                img      = np.array(sct.grab(monitor))[:, :, :3]
                cyan_ok, is_death, white_ratio, left_cyan, right_cyan = check_icon_state(img, wt, wr)

                is_playing = ow_focus and cyan_ok

                ow_str    = "✅OW " if ow_focus    else "❌OW "
                cyan_str  = "✅水色" if cyan_ok     else "❌水色"
                white_bar = "#" * int(white_ratio * 30)
                white_str = f"白:{white_ratio:.2f}[{white_bar:<30}]"

                if is_death and is_playing:
                    status = "💀 DEATH!"
                elif is_playing:
                    status = "🎮 PLAYING"
                else:
                    status = "😴 待機中 "

                print(f"\r{ow_str} {cyan_str} {white_str} {status}   ", end='', flush=True)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n終了")


def main():
    config = load_config()
    live_monitor(config)


if __name__ == '__main__':
    main()
