#!/usr/bin/env python3
"""
Overwatch 2 Death Detector
プレイ中 & デス判定: OWフォアグラウンド AND 左右端水色（G>90, B>130）
デス:               白ピクセル割合 >= 閾値
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


def get_edge_rgb(img_bgr, edge=10):
    """左右端の中央50%のBGR平均"""
    h = img_bgr.shape[0]
    y1, y2 = h // 4, h * 3 // 4
    lb = img_bgr[y1:y2, :edge,  :].mean(axis=(0, 1))
    rb = img_bgr[y1:y2, -edge:, :].mean(axis=(0, 1))
    return lb, rb


def is_cyan(bgr):
    """水色判定: G>90 and B>130"""
    b, g, r = bgr
    return g > 90 and b > 130


def check_state(img_bgr, white_threshold=180, white_ratio_trigger=0.25):
    lb, rb = get_edge_rgb(img_bgr)
    lc = is_cyan(lb)
    rc = is_cyan(rb)
    cyan_ok = lc and rc
    white_ratio = np.all(img_bgr > white_threshold, axis=2).mean()
    is_death = white_ratio >= white_ratio_trigger
    return cyan_ok, is_death, white_ratio, lc, rc


class DeathDetector:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.access_token        = self.config['pavlok']['access_token']
        self.zap_intensity       = self.config['pavlok']['zap_intensity']
        self.fps                 = self.config['monitor']['fps']
        self.cooldown_seconds    = self.config['monitor']['cooldown_seconds']
        self.watch_region        = self.config['monitor']['watch_region']
        self.white_threshold     = self.config['monitor'].get('white_threshold', 180)
        self.white_ratio_trigger = self.config['monitor'].get('white_ratio_trigger', 0.25)
        self.confirm_frames      = self.config['monitor'].get('confirm_frames', 1)

        self.last_zap_time = None
        self.was_playing   = False
        self.death_counter = 0
        self.sct           = mss()

        print(f"[{self._ts()}] Death Detector 起動")
        print(f"監視: x={self.watch_region['x']}, y={self.watch_region['y']}, "
              f"w={self.watch_region['width']}, h={self.watch_region['height']}")
        print(f"プレイ中 & デス: OWフォーカス AND 水色(G>90,B>130) → 白:{self.white_ratio_trigger}")
        print(f"電撃強度: {self.zap_intensity} | クールダウン: {self.cooldown_seconds}秒\n")

    def _ts(self):
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def capture(self):
        w = self.watch_region
        m = {'left': w['x'], 'top': w['y'], 'width': w['width'], 'height': w['height']}
        return np.array(self.sct.grab(m))[:, :, :3]

    def send_zap(self):
        try:
            r = requests.post(
                "https://api.pavlok.com/api/v5/stimulus/send",
                headers={'Authorization': f'Bearer {self.access_token}', 'Content-Type': 'application/json'},
                json={"stimulus": {"stimulusType": "zap", "stimulusValue": self.zap_intensity}},
                timeout=5
            )
            if r.status_code == 200:
                print(f"[{self._ts()}] ⚡ 電撃送信成功 (強度: {self.zap_intensity})")
                return True
            print(f"[{self._ts()}] ⚠ API エラー: {r.status_code}")
        except Exception as e:
            print(f"[{self._ts()}] ⚠ 通信エラー: {e}")
        return False

    def in_cooldown(self):
        if self.last_zap_time is None:
            return False
        return (datetime.now() - self.last_zap_time).total_seconds() < self.cooldown_seconds

    def run(self):
        interval = 1.0 / self.fps
        print(f"[{self._ts()}] 監視開始...")
        try:
            while True:
                t0 = time.time()
                ow_focus = is_ow_foreground()
                img = self.capture()
                cyan_ok, is_death, white_ratio, lc, rc = check_state(
                    img, self.white_threshold, self.white_ratio_trigger
                )

                is_playing = ow_focus and cyan_ok

                if is_playing and not self.was_playing:
                    print(f"[{self._ts()}] 🎮 プレイ中検知！監視開始。")
                elif not is_playing and self.was_playing:
                    print(f"[{self._ts()}] プレイ終了。待機中。")
                    self.death_counter = 0
                self.was_playing = is_playing

                if is_playing:
                    if is_death:
                        self.death_counter += 1
                        if self.death_counter == 1:
                            print(f"[{self._ts()}] 💀 デス検知! 白:{white_ratio:.3f}")
                        if self.death_counter >= self.confirm_frames:
                            if self.in_cooldown():
                                rem = self.cooldown_seconds - (datetime.now() - self.last_zap_time).total_seconds()
                                print(f"[{self._ts()}] ⏳ クールダウン (残り {rem:.1f}秒)")
                            else:
                                print(f"[{self._ts()}] 💀 デス確定！電撃発動")
                                if self.send_zap():
                                    self.last_zap_time = datetime.now()
                            self.death_counter = 0
                    else:
                        self.death_counter = 0

                time.sleep(max(0, interval - (time.time() - t0)))

        except KeyboardInterrupt:
            print(f"\n[{self._ts()}] 停止")
        finally:
            self.sct.close()


if __name__ == '__main__':
    detector = DeathDetector()
    detector.run()
