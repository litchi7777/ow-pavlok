#!/usr/bin/env python3
"""キャリブレーションツール - リアルタイムモニター"""
import sys, time, numpy as np, yaml
from mss import mss

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

def main():
    config = load_config()
    watch = config['monitor']['watch_region']
    wt    = config['monitor'].get('white_threshold', 180)
    wr    = config['monitor'].get('white_ratio_trigger', 0.25)
    edge  = 10

    monitor = {'left': watch['x'], 'top': watch['y'], 'width': watch['width'], 'height': watch['height']}
    print("=== リアルタイムモニター (Ctrl+C で終了) ===")
    print("L/R = 左右端 RGB | 水色条件: G>100, B>140, B>R+60\n")

    with mss() as sct:
        try:
            while True:
                ow_focus = is_ow_foreground()
                img = np.array(sct.grab(monitor))[:, :, :3]  # BGR

                lb = img[:, :edge, :].mean(axis=(0,1))   # [B,G,R]
                rb = img[:, -edge:, :].mean(axis=(0,1))

                def cyan(bgr):
                    b,g,r = bgr
                    return g > 100 and b > 140 and b > r + 60

                lc = cyan(lb); rc = cyan(rb)
                cyan_ok = lc and rc

                white_ratio = np.all(img > wt, axis=2).mean()
                is_death    = white_ratio >= wr
                is_playing  = ow_focus and cyan_ok

                ow_s   = "✅OW" if ow_focus  else "❌OW"
                cyan_s = "✅水" if cyan_ok   else "❌水"
                bar    = "#" * int(white_ratio * 20)

                if is_death and is_playing:   st = "💀DEATH!"
                elif is_playing:              st = "🎮PLAY  "
                else:                         st = "😴待機  "

                print(f"\r{ow_s} {cyan_s} "
                      f"L:R{lb[2]:.0f}G{lb[1]:.0f}B{lb[0]:.0f} "
                      f"R:R{rb[2]:.0f}G{rb[1]:.0f}B{rb[0]:.0f} "
                      f"白:{white_ratio:.2f}[{bar:<20}] {st}  ",
                      end='', flush=True)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n終了")

if __name__ == '__main__':
    main()
