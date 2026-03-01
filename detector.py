#!/usr/bin/env python3
"""
Overwatch 2 Death Detector
- OWがフォアグラウンドの時のみ監視
- 連続N回検知して初めて電撃（一瞬のフォーカスを弾く）
- 電撃直前にもOWアクティブを再確認
"""
import time
import numpy as np
import requests
import yaml
import sys
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


class DeathDetector:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.access_token = self.config['pavlok']['access_token']
        self.zap_intensity = self.config['pavlok']['zap_intensity']
        self.fps = self.config['monitor']['fps']
        self.cooldown_seconds = self.config['monitor']['cooldown_seconds']
        self.watch_region = self.config['monitor']['watch_region']
        self.white_threshold = self.config['monitor'].get('white_threshold', 180)
        self.white_ratio_trigger = self.config['monitor'].get('white_ratio_trigger', 0.25)
        # 連続N回検知で初めて電撃（デフォルト3回 = 0.3秒）
        self.confirm_frames = self.config['monitor'].get('confirm_frames', 3)

        self.last_zap_time = None
        self.ow_was_active = False
        self.death_counter = 0  # 連続検知カウンタ
        self.sct = mss()

        print(f"[{self._ts()}] Death Detector 起動")
        print(f"監視領域: x={self.watch_region['x']}, y={self.watch_region['y']}, "
              f"w={self.watch_region['width']}, h={self.watch_region['height']}")
        print(f"FPS: {self.fps} | 白ピクセル閾値: {self.white_threshold} | 発動割合: {self.white_ratio_trigger}")
        print(f"電撃強度: {self.zap_intensity} | クールダウン: {self.cooldown_seconds}秒")
        print(f"確認フレーム数: {self.confirm_frames}回連続検知で電撃\n")
        print(f"[{self._ts()}] OWがアクティブになるのを待機中...")

    def _ts(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def capture_region(self):
        monitor = {
            'left': self.watch_region['x'],
            'top': self.watch_region['y'],
            'width': self.watch_region['width'],
            'height': self.watch_region['height']
        }
        screenshot = self.sct.grab(monitor)
        return np.array(screenshot)[:, :, :3]

    def detect_death(self, img_bgr):
        white_mask = np.all(img_bgr > self.white_threshold, axis=2)
        white_ratio = white_mask.mean()
        return white_ratio >= self.white_ratio_trigger, white_ratio

    def send_zap(self):
        try:
            url = "https://api.pavlok.com/api/v5/stimulus/send"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            payload = {"stimulus": {"stimulusType": "zap", "stimulusValue": self.zap_intensity}}
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            if response.status_code == 200:
                print(f"[{self._ts()}] ⚡ 電撃送信成功 (強度: {self.zap_intensity})")
                return True
            else:
                print(f"[{self._ts()}] ⚠ API エラー: {response.status_code}")
                return False
        except Exception as e:
            print(f"[{self._ts()}] ⚠ 通信エラー: {e}")
            return False

    def is_cooldown(self):
        if self.last_zap_time is None:
            return False
        return (datetime.now() - self.last_zap_time).total_seconds() < self.cooldown_seconds

    def run(self):
        interval = 1.0 / self.fps

        try:
            while True:
                t = time.time()
                ow_active = is_ow_foreground()

                if not ow_active:
                    if self.ow_was_active:
                        print(f"[{self._ts()}] OWが非アクティブ。監視一時停止。")
                        self.ow_was_active = False
                    self.death_counter = 0  # OW離れたらカウンタリセット
                    time.sleep(1)
                    continue

                if not self.ow_was_active:
                    print(f"[{self._ts()}] OWがアクティブ！監視開始。")
                    self.ow_was_active = True

                img = self.capture_region()
                is_death, ratio = self.detect_death(img)

                if is_death:
                    self.death_counter += 1
                    if self.death_counter == 1:
                        print(f"[{self._ts()}] 💀 デス候補検知 ({self.death_counter}/{self.confirm_frames}) 白割合: {ratio:.3f}")

                    if self.death_counter >= self.confirm_frames:
                        # 電撃直前にOWがまだアクティブか再確認
                        if not is_ow_foreground():
                            print(f"[{self._ts()}] ⚠ 電撃直前にOW非アクティブ検知 → キャンセル")
                            self.death_counter = 0
                        elif self.is_cooldown():
                            rem = self.cooldown_seconds - (datetime.now() - self.last_zap_time).total_seconds()
                            print(f"[{self._ts()}] ⏳ クールダウン中 (残り {rem:.1f}秒)")
                            self.death_counter = 0
                        else:
                            print(f"[{self._ts()}] 💀 デス確定！電撃発動")
                            if self.send_zap():
                                self.last_zap_time = datetime.now()
                            self.death_counter = 0
                else:
                    self.death_counter = 0  # 検知途切れたらリセット

                time.sleep(max(0, interval - (time.time() - t)))

        except KeyboardInterrupt:
            print(f"\n[{self._ts()}] 停止")
        finally:
            self.sct.close()


if __name__ == '__main__':
    detector = DeathDetector()
    detector.run()
