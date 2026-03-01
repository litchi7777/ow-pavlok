#!/usr/bin/env python3
"""
Overwatch 2 Death Detector
判定ロジック:
  プレイ中判定: アイコン左右端が水色 = OWでプレイヤーとしてプレイ中
  デス判定:    白ピクセル割合が閾値以上（ドクロアニメで水色フレームが崩れ白が急増）
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


def check_icon_state(img_bgr, white_threshold=180, white_ratio_trigger=0.25):
    """
    アイコン領域の状態を判定
    戻り値: (is_playing, is_death, white_ratio, left_cyan, right_cyan)
      - is_playing: 左右端が水色 = プレイヤーとしてプレイ中
      - is_death:   白ピクセル急増 = デス
    """
    h, w = img_bgr.shape[:2]
    edge = 10  # 端から何pxを水色チェックするか

    # 左端・右端の平均色 (BGR)
    left_bgr  = img_bgr[:, :edge, :].mean(axis=(0, 1))   # [B, G, R]
    right_bgr = img_bgr[:, -edge:, :].mean(axis=(0, 1))

    def is_cyan_bgr(bgr):
        b, g, r = bgr
        return g > 100 and b > 140 and b > r + 60

    left_cyan  = is_cyan_bgr(left_bgr)
    right_cyan = is_cyan_bgr(right_bgr)
    is_playing = left_cyan and right_cyan

    # 白ピクセル割合
    white_mask  = np.all(img_bgr > white_threshold, axis=2)
    white_ratio = white_mask.mean()
    is_death    = white_ratio >= white_ratio_trigger

    return is_playing, is_death, white_ratio, left_cyan, right_cyan


class DeathDetector:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.access_token      = self.config['pavlok']['access_token']
        self.zap_intensity     = self.config['pavlok']['zap_intensity']
        self.fps               = self.config['monitor']['fps']
        self.cooldown_seconds  = self.config['monitor']['cooldown_seconds']
        self.watch_region      = self.config['monitor']['watch_region']
        self.white_threshold   = self.config['monitor'].get('white_threshold', 180)
        self.white_ratio_trigger = self.config['monitor'].get('white_ratio_trigger', 0.25)
        self.confirm_frames    = self.config['monitor'].get('confirm_frames', 1)

        self.last_zap_time   = None
        self.was_playing     = False
        self.death_counter   = 0
        self.sct             = mss()

        print(f"[{self._ts()}] Death Detector 起動")
        print(f"監視領域: x={self.watch_region['x']}, y={self.watch_region['y']}, "
              f"w={self.watch_region['width']}, h={self.watch_region['height']}")
        print(f"FPS: {self.fps} | 白割合閾値: {self.white_ratio_trigger} | 確認フレーム: {self.confirm_frames}")
        print(f"電撃強度: {self.zap_intensity} | クールダウン: {self.cooldown_seconds}秒")
        print(f"プレイ中判定: 左右端が水色かどうか（ウィンドウフォーカス不要）\n")
        print(f"[{self._ts()}] 監視中... (OWでプレイ開始したら自動検知)")

    def _ts(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def capture_region(self):
        monitor = {
            'left':   self.watch_region['x'],
            'top':    self.watch_region['y'],
            'width':  self.watch_region['width'],
            'height': self.watch_region['height']
        }
        return np.array(self.sct.grab(monitor))[:, :, :3]  # BGR

    def send_zap(self):
        try:
            url     = "https://api.pavlok.com/api/v5/stimulus/send"
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

                img = self.capture_region()
                is_playing, is_death, white_ratio, left_cyan, right_cyan = check_icon_state(
                    img, self.white_threshold, self.white_ratio_trigger
                )

                # プレイ中状態の変化をログ
                if is_playing and not self.was_playing:
                    print(f"[{self._ts()}] 🎮 プレイ中検知！監視開始。")
                elif not is_playing and self.was_playing:
                    print(f"[{self._ts()}] OWプレイ終了。監視停止。")
                    self.death_counter = 0
                self.was_playing = is_playing

                if not is_playing:
                    self.death_counter = 0
                    time.sleep(max(0, interval - (time.time() - t)))
                    continue

                # デス判定
                if is_death:
                    self.death_counter += 1
                    if self.death_counter == 1:
                        print(f"[{self._ts()}] 💀 デス検知! 白:{white_ratio:.2f} ({self.death_counter}/{self.confirm_frames})")

                    if self.death_counter >= self.confirm_frames:
                        if self.is_cooldown():
                            rem = self.cooldown_seconds - (datetime.now() - self.last_zap_time).total_seconds()
                            print(f"[{self._ts()}] ⏳ クールダウン (残り {rem:.1f}秒)")
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
