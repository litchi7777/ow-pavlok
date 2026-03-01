#!/usr/bin/env python3
"""
Overwatch 2 Death Detector
- OWが3秒間フォアグラウンドを維持したら「プレイ中」と判定
- 連続N回検知で電撃（一瞬のフォーカスを弾く）
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
        self.confirm_frames = self.config['monitor'].get('confirm_frames', 3)
        # OWが連続してアクティブな時間がこれ以上続いたらプレイ中と判定（秒）
        self.active_confirm_sec = self.config['monitor'].get('active_confirm_sec', 3)

        self.last_zap_time = None
        self.is_playing = False       # 「プレイ中」状態
        self.ow_active_since = None   # OWがアクティブになった時刻
        self.death_counter = 0
        self.sct = mss()

        print(f"[{self._ts()}] Death Detector 起動")
        print(f"監視領域: x={self.watch_region['x']}, y={self.watch_region['y']}, "
              f"w={self.watch_region['width']}, h={self.watch_region['height']}")
        print(f"FPS: {self.fps} | 白割合閾値: {self.white_ratio_trigger} | 確認フレーム: {self.confirm_frames}")
        print(f"プレイ判定: OWが{self.active_confirm_sec}秒継続でプレイ中と判断")
        print(f"電撃強度: {self.zap_intensity} | クールダウン: {self.cooldown_seconds}秒\n")
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
        return np.array(self.sct.grab(monitor))[:, :, :3]

    def detect_death(self, img_bgr):
        white_mask = np.all(img_bgr > self.white_threshold, axis=2)
        ratio = white_mask.mean()
        return ratio >= self.white_ratio_trigger, ratio

    def send_zap(self):
        try:
            url = "https://api.pavlok.com/api/v5/stimulus/send"
            headers = {'Authorization': f'Bearer {self.access_token}', 'Content-Type': 'application/json'}
            payload = {"stimulus": {"stimulusType": "zap", "stimulusValue": self.zap_intensity}}
            r = requests.post(url, headers=headers, json=payload, timeout=5)
            if r.status_code == 200:
                print(f"[{self._ts()}] ⚡ 電撃送信成功 (強度: {self.zap_intensity})")
                return True
            print(f"[{self._ts()}] ⚠ API エラー: {r.status_code}")
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

                if ow_active:
                    if self.ow_active_since is None:
                        self.ow_active_since = datetime.now()

                    active_duration = (datetime.now() - self.ow_active_since).total_seconds()

                    if not self.is_playing and active_duration >= self.active_confirm_sec:
                        self.is_playing = True
                        print(f"[{self._ts()}] 🎮 OW {self.active_confirm_sec}秒継続 → プレイ中と判定！監視開始。")

                else:
                    # OWが非アクティブになった
                    if self.is_playing:
                        print(f"[{self._ts()}] OWが非アクティブ。プレイ中断と判定。監視停止。")
                    elif self.ow_active_since is not None:
                        pass  # 3秒未満で離れた → プレイ判定せずリセット
                    self.is_playing = False
                    self.ow_active_since = None
                    self.death_counter = 0
                    time.sleep(1)
                    continue

                # プレイ中でない（アクティブだが3秒未満）→ 待機
                if not self.is_playing:
                    time.sleep(0.5)
                    continue

                # プレイ中 → 検知
                img = self.capture_region()
                is_death, ratio = self.detect_death(img)

                if is_death:
                    self.death_counter += 1
                    if self.death_counter == 1:
                        print(f"[{self._ts()}] 💀 デス候補 ({self.death_counter}/{self.confirm_frames}) 白割合: {ratio:.3f}")

                    if self.death_counter >= self.confirm_frames:
                        if not is_ow_foreground():
                            print(f"[{self._ts()}] ⚠ 電撃直前にOW非アクティブ → キャンセル")
                            self.death_counter = 0
                            self.is_playing = False
                            self.ow_active_since = None
                        elif self.is_cooldown():
                            rem = self.cooldown_seconds - (datetime.now() - self.last_zap_time).total_seconds()
                            print(f"[{self._ts()}] ⏳ クールダウン (残り {rem:.1f}秒)")
                            self.death_counter = 0
                        else:
                            print(f"[{self._ts()}] 💀 デス確定！電撃発動")
                            if self.send_zap():
                                self.last_zap_time = datetime.now()
                            self.death_counter = 0
                else:
                    self.death_counter = 0

                time.sleep(max(0, interval - (time.time() - t)))

        except KeyboardInterrupt:
            print(f"\n[{self._ts()}] 停止")
        finally:
            self.sct.close()


if __name__ == '__main__':
    detector = DeathDetector()
    detector.run()
