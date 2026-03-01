#!/usr/bin/env python3
"""
Overwatch 2 Death Detector
デス状態をスクリーンキャプチャで検知してPavlok APIで電撃するスクリプト
"""
import time
import cv2
import numpy as np
import requests
import yaml
from mss import mss
from datetime import datetime, timedelta


class DeathDetector:
    def __init__(self, config_path='config.yaml'):
        # 設定ファイル読み込み
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # テンプレート画像読み込み
        self.template = cv2.imread('skull_template.png', cv2.IMREAD_GRAYSCALE)
        if self.template is None:
            raise FileNotFoundError("skull_template.png が見つかりません")

        # 設定取得
        self.access_token = self.config['pavlok']['access_token']
        self.zap_intensity = self.config['pavlok']['zap_intensity']
        self.fps = self.config['monitor']['fps']
        self.match_threshold = self.config['monitor']['match_threshold']
        self.cooldown_seconds = self.config['monitor']['cooldown_seconds']
        self.watch_region = self.config['monitor']['watch_region']

        # クールダウン管理
        self.last_zap_time = None

        # mss初期化
        self.sct = mss()

        print(f"[{self._timestamp()}] Death Detector 起動")
        print(f"監視領域: x={self.watch_region['x']}, y={self.watch_region['y']}, "
              f"w={self.watch_region['width']}, h={self.watch_region['height']}")
        print(f"マッチ閾値: {self.match_threshold}")
        print(f"電撃強度: {self.zap_intensity}")
        print(f"クールダウン: {self.cooldown_seconds}秒\n")

    def _timestamp(self):
        """現在時刻の文字列を返す"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def capture_region(self):
        """監視領域をキャプチャしてグレースケール画像を返す"""
        monitor = {
            'left': self.watch_region['x'],
            'top': self.watch_region['y'],
            'width': self.watch_region['width'],
            'height': self.watch_region['height']
        }

        # スクリーンキャプチャ
        screenshot = self.sct.grab(monitor)

        # numpy配列に変換してグレースケール化
        img = np.array(screenshot)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)

        return img_gray

    def detect_death(self, img_gray):
        """テンプレートマッチングでデス状態を検知"""
        result = cv2.matchTemplate(img_gray, self.template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        # マッチ率が閾値を超えたらデス判定
        if max_val >= self.match_threshold:
            return True, max_val
        return False, max_val

    def send_zap(self):
        """Pavlok APIで電撃を送る"""
        try:
            url = "https://api.pavlok.com/api/v5/stimulus/send"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            payload = {
                "stimulus": {
                    "stimulusType": "zap",
                    "stimulusValue": self.zap_intensity
                }
            }

            response = requests.post(url, headers=headers, json=payload, timeout=5)

            if response.status_code == 200:
                print(f"[{self._timestamp()}] ⚡ Pavlok 電撃送信成功 (強度: {self.zap_intensity})")
                return True
            else:
                print(f"[{self._timestamp()}] ⚠ Pavlok API エラー: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"[{self._timestamp()}] ⚠ Pavlok API 通信エラー: {e}")
            return False

    def is_cooldown_active(self):
        """クールダウン中かどうかを判定"""
        if self.last_zap_time is None:
            return False

        elapsed = datetime.now() - self.last_zap_time
        return elapsed.total_seconds() < self.cooldown_seconds

    def run(self):
        """メイン監視ループ"""
        interval = 1.0 / self.fps

        try:
            while True:
                loop_start = time.time()

                # 画面キャプチャ
                img_gray = self.capture_region()

                # デス検知
                is_death, match_score = self.detect_death(img_gray)

                if is_death:
                    print(f"[{self._timestamp()}] 💀 デス検知! (マッチ率: {match_score:.3f})")

                    # クールダウン確認
                    if self.is_cooldown_active():
                        remaining = self.cooldown_seconds - (datetime.now() - self.last_zap_time).total_seconds()
                        print(f"[{self._timestamp()}] ⏳ クールダウン中 (残り {remaining:.1f}秒)")
                    else:
                        # 電撃実行
                        if self.send_zap():
                            self.last_zap_time = datetime.now()

                # FPS調整
                elapsed = time.time() - loop_start
                sleep_time = max(0, interval - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print(f"\n[{self._timestamp()}] Death Detector 停止")
        finally:
            self.sct.close()


if __name__ == '__main__':
    detector = DeathDetector()
    detector.run()
