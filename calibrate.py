#!/usr/bin/env python3
"""
キャリブレーションツール
監視領域の確認・調整用にスクリーンショットを保存
"""
import cv2
import numpy as np
import yaml
from mss import mss
from datetime import datetime


def load_config(config_path='config.yaml'):
    """設定ファイル読み込み"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def capture_watch_region(config):
    """監視領域をキャプチャして保存"""
    watch_region = config['monitor']['watch_region']

    monitor = {
        'left': watch_region['x'],
        'top': watch_region['y'],
        'width': watch_region['width'],
        'height': watch_region['height']
    }

    with mss() as sct:
        # スクリーンキャプチャ
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)

        # BGRAからBGRに変換（保存用）
        img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        # タイムスタンプ付きファイル名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f'bottom_left_region_{timestamp}.png'

        # 保存
        cv2.imwrite(output_path, img_bgr)

        print(f"監視領域をキャプチャしました: {output_path}")
        print(f"座標: x={watch_region['x']}, y={watch_region['y']}")
        print(f"サイズ: {watch_region['width']}x{watch_region['height']}")

        return output_path


def test_template_matching(config, region_image_path):
    """テンプレートマッチングのテスト"""
    # テンプレート読み込み
    template = cv2.imread('skull_template.png', cv2.IMREAD_GRAYSCALE)
    if template is None:
        print("エラー: skull_template.png が見つかりません")
        return

    # キャプチャ画像読み込み
    img = cv2.imread(region_image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"エラー: {region_image_path} が見つかりません")
        return

    # テンプレートマッチング
    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    threshold = config['monitor']['match_threshold']

    print(f"\n--- テンプレートマッチング結果 ---")
    print(f"最大マッチ率: {max_val:.3f}")
    print(f"閾値: {threshold}")

    if max_val >= threshold:
        print("✅ デス状態を検知しました!")
        print(f"検知位置: x={max_loc[0]}, y={max_loc[1]}")
    else:
        print("❌ デス状態は検知されませんでした")
        print("ヒント: デス画面で再度実行するか、config.yamlの閾値を調整してください")


def main():
    print("=== Overwatch 2 Death Detector キャリブレーション ===\n")

    # 設定読み込み
    config = load_config()

    # 監視領域をキャプチャ
    print("3秒後にスクリーンショットを撮影します...")
    print("Overwatchのゲーム画面を表示してください\n")

    import time
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)

    region_image = capture_watch_region(config)

    # テンプレートマッチングのテスト
    print("\nテンプレートマッチングをテストします...\n")
    test_template_matching(config, region_image)

    print("\n完了! 保存された画像を確認して、必要に応じてconfig.yamlの座標を調整してください。")


if __name__ == '__main__':
    main()
