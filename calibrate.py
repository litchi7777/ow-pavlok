#!/usr/bin/env python3
"""
キャリブレーションツール - 白ピクセル割合の確認用
"""
import cv2
import numpy as np
import yaml
import time
from mss import mss
from datetime import datetime


def load_config(config_path='config.yaml'):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def capture_watch_region(config):
    watch_region = config['monitor']['watch_region']
    monitor = {
        'left': watch_region['x'],
        'top': watch_region['y'],
        'width': watch_region['width'],
        'height': watch_region['height']
    }
    with mss() as sct:
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f'calibrate_{timestamp}.png'
        cv2.imwrite(output_path, img_bgr)
        print(f"キャプチャ保存: {output_path}")
        return img_bgr


def analyze_white_ratio(img_bgr, config):
    threshold = config['monitor'].get('white_threshold', 180)
    trigger = config['monitor'].get('white_ratio_trigger', 0.25)
    white_mask = np.all(img_bgr > threshold, axis=2)
    ratio = white_mask.mean()
    print(f"\n--- 白ピクセル分析 ---")
    print(f"白ピクセル割合: {ratio:.3f} ({ratio*100:.1f}%)")
    print(f"発動閾値: {trigger} ({trigger*100:.1f}%)")
    if ratio >= trigger:
        print("💀 デス判定！")
    else:
        print(f"✅ 通常状態 (あと {(trigger-ratio)*100:.1f}% で発動)")
    return ratio


def live_monitor(config):
    print("\n=== リアルタイムモニター（Ctrl+Cで終了）===")
    watch_region = config['monitor']['watch_region']
    threshold = config['monitor'].get('white_threshold', 180)
    trigger = config['monitor'].get('white_ratio_trigger', 0.25)
    monitor = {
        'left': watch_region['x'],
        'top': watch_region['y'],
        'width': watch_region['width'],
        'height': watch_region['height']
    }
    with mss() as sct:
        try:
            while True:
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)[:, :, :3]
                white_mask = np.all(img > threshold, axis=2)
                ratio = white_mask.mean()
                bar = '#' * int(ratio * 40)
                status = 'DEATH!' if ratio >= trigger else 'alive '
                print(f"\r白: {ratio:.3f} [{bar:<40}] {status}   ", end='', flush=True)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n終了")


def main():
    print("=== OW Pavlok キャリブレーション ===\n")
    config = load_config()
    print("1. スクリーンショット撮影 + 分析")
    print("2. リアルタイムモニター（デス状態で数値確認）")
    choice = input("\n番号: ").strip()

    if choice == '2':
        live_monitor(config)
    else:
        print("\n3秒後に撮影します...")
        for i in range(3, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        img_bgr = capture_watch_region(config)
        analyze_white_ratio(img_bgr, config)
        print("\n閾値調整は config.yaml の white_ratio_trigger を変更してください")


if __name__ == '__main__':
    main()
