#!/usr/bin/env python3
"""
キャリブレーションツール
- リアルタイムモニター（RGB値・min/max・ログ保存）
- スクリーンショット撮影モード
"""
import sys, time, numpy as np, yaml, cv2
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
        return any(kw in win32gui.GetWindowText(hwnd).lower() for kw in OW_WINDOW_KEYWORDS)
    except:
        return False

def load_config(p='config.yaml'):
    with open(p, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_edge_rgb(img_bgr, edge=10):
    """左右端の中央50%のRGB平均を返す（上下端を除外）"""
    h = img_bgr.shape[0]
    y1, y2 = h // 4, h * 3 // 4  # 中央50%
    lb = img_bgr[y1:y2, :edge, :].mean(axis=(0,1))   # [B,G,R]
    rb = img_bgr[y1:y2, -edge:, :].mean(axis=(0,1))
    return lb, rb

def is_cyan(bgr, g_min=90, b_min=130, b_r_diff=0):
    b, g, r = bgr
    return g > g_min and b > b_min

def capture_region(sct, watch):
    monitor = {'left': watch['x'], 'top': watch['y'], 'width': watch['width'], 'height': watch['height']}
    return np.array(sct.grab(monitor))[:, :, :3]

def screenshot_mode(config):
    """3秒後にスクリーンショットを撮影して保存"""
    watch = config['monitor']['watch_region']
    wt    = config['monitor'].get('white_threshold', 180)
    wr    = config['monitor'].get('white_ratio_trigger', 0.25)
    print("\n3秒後にスクリーンショットを撮影します...")
    for i in range(3, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    with mss() as sct:
        img = capture_region(sct, watch)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = f'calibrate_{ts}.png'
        cv2.imwrite(path, img)
        lb, rb = get_edge_rgb(img)
        white_ratio = np.all(img > wt, axis=2).mean()
        print(f"\n保存: {path}")
        print(f"左端(中央) RGB: R={lb[2]:.0f} G={lb[1]:.0f} B={lb[0]:.0f} → 水色:{is_cyan(lb)}")
        print(f"右端(中央) RGB: R={rb[2]:.0f} G={rb[1]:.0f} B={rb[0]:.0f} → 水色:{is_cyan(rb)}")
        print(f"白ピクセル割合: {white_ratio:.3f} (閾値: {wr})")

def live_monitor(config):
    """リアルタイムモニター（ログファイルにmin/max記録）"""
    watch = config['monitor']['watch_region']
    wt    = config['monitor'].get('white_threshold', 180)
    wr    = config['monitor'].get('white_ratio_trigger', 0.25)

    log_path = f"calibrate_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    print(f"=== リアルタイムモニター (Ctrl+C で終了) ===")
    print(f"ログ保存先: {log_path}")
    print("L/R = 左右端中央のRGB | 水色条件: G>100, B>140, B>R+60\n")

    # min/max追跡
    stats = {
        'L_R': [999,0], 'L_G': [999,0], 'L_B': [999,0],
        'R_R': [999,0], 'R_G': [999,0], 'R_B': [999,0],
        'white': [999.0, 0.0]
    }

    with open(log_path, 'w') as logf:
        logf.write("time,ow_focus,left_cyan,right_cyan,L_R,L_G,L_B,R_R,R_G,R_B,white_ratio,is_playing,is_death\n")

        with mss() as sct:
            try:
                while True:
                    ow_focus = is_ow_foreground()
                    img = capture_region(sct, watch)
                    lb, rb = get_edge_rgb(img)
                    lc = is_cyan(lb); rc = is_cyan(rb)
                    cyan_ok = lc and rc
                    white_ratio = np.all(img > wt, axis=2).mean()
                    is_death   = white_ratio >= wr
                    is_playing = ow_focus and cyan_ok

                    # min/max更新
                    for key, val in [('L_R',lb[2]),('L_G',lb[1]),('L_B',lb[0]),
                                     ('R_R',rb[2]),('R_G',rb[1]),('R_B',rb[0])]:
                        if val < stats[key][0]: stats[key][0] = val
                        if val > stats[key][1]: stats[key][1] = val
                    if white_ratio < stats['white'][0]: stats['white'][0] = white_ratio
                    if white_ratio > stats['white'][1]: stats['white'][1] = white_ratio

                    # ログ書き込み
                    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    logf.write(f"{ts},{ow_focus},{lc},{rc},{lb[2]:.0f},{lb[1]:.0f},{lb[0]:.0f},"
                               f"{rb[2]:.0f},{rb[1]:.0f},{rb[0]:.0f},{white_ratio:.4f},{is_playing},{is_death}\n")
                    logf.flush()

                    # 表示
                    ow_s   = "✅OW" if ow_focus  else "❌OW"
                    cyan_s = "✅水" if cyan_ok   else "❌水"
                    bar    = "#" * int(white_ratio * 20)

                    if is_death and is_playing:   st = "💀DEATH!"
                    elif is_playing:              st = "🎮PLAY  "
                    else:                         st = "😴待機  "

                    print(f"\r{ow_s} {cyan_s} "
                          f"L:R{lb[2]:.0f}G{lb[1]:.0f}B{lb[0]:.0f} "
                          f"R:R{rb[2]:.0f}G{rb[1]:.0f}B{rb[0]:.0f} "
                          f"白:{white_ratio:.3f}[{bar:<20}] {st}  ",
                          end='', flush=True)
                    time.sleep(0.1)

            except KeyboardInterrupt:
                print(f"\n\n=== min/max サマリー ===")
                print(f"左端 R: {stats['L_R'][0]:.0f} ~ {stats['L_R'][1]:.0f}")
                print(f"左端 G: {stats['L_G'][0]:.0f} ~ {stats['L_G'][1]:.0f}")
                print(f"左端 B: {stats['L_B'][0]:.0f} ~ {stats['L_B'][1]:.0f}")
                print(f"右端 R: {stats['R_R'][0]:.0f} ~ {stats['R_R'][1]:.0f}")
                print(f"右端 G: {stats['R_G'][0]:.0f} ~ {stats['R_G'][1]:.0f}")
                print(f"右端 B: {stats['R_B'][0]:.0f} ~ {stats['R_B'][1]:.0f}")
                print(f"白割合: {stats['white'][0]:.3f} ~ {stats['white'][1]:.3f}")
                print(f"\nログ保存済み: {log_path}")

def main():
    config = load_config()
    print("=== OW Pavlok キャリブレーション ===\n")
    print("1. リアルタイムモニター（ログ・min/max記録）")
    print("2. スクリーンショット撮影")
    choice = input("\n番号: ").strip()
    if choice == '2':
        screenshot_mode(config)
    else:
        live_monitor(config)

if __name__ == '__main__':
    main()
