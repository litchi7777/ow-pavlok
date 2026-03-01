# OW Death Detector - 実装タスク

## 概要
Overwatch 2のデス状態をスクリーンキャプチャで検知して、Pavlok APIで電撃するWindowsアプリ。

## 検知方法
- 左下のヒーローポートレートがドクロアイコンに変わったらデス判定
- テンプレートマッチング（OpenCV）で検知

## サンプルデータ
- `death_screen_sample.png`: デス時のスクショ（1663x932）
- `skull_template.png`: ドクロアイコンのテンプレート（70x55, 座標: x=60-130, y=792-847）

## 監視領域
- 元画像サイズ: 1663x932（ゲームのウィンドウサイズに応じてスケール調整が必要）
- 監視座標（1920x1080基準）: 左下 x=0-200, y=830-960 あたり
- ユーザーのモニターは1920x1080と仮定（設定で変更可能）

## ファイル構成
```
ow-death-detector/
├── README.md
├── detector.py          # メイン監視スクリプト（Windowsで動かす）
├── config.yaml          # 設定ファイル
├── calibrate.py         # 座標キャリブレーションツール
├── requirements.txt
└── skull_template.png   # テンプレート画像
```

## detector.py の仕様
- `mss` でスクリーンキャプチャ（1秒に2回程度）
- OpenCVのテンプレートマッチング（`cv2.matchTemplate`）
- 監視領域: 左下エリアのみ（CPU負荷軽減）
- マッチ率 > 0.7 でデス判定
- デス検知→Pavlok API呼び出し（curlではなくrequests）
- 電撃後は10秒クールダウン（連続電撃防止）
- コンソールにログ出力

## config.yaml の内容
```yaml
pavlok:
  access_token: "YOUR_TOKEN_HERE"
  zap_intensity: 30

monitor:
  fps: 2                    # キャプチャ頻度（秒間）
  match_threshold: 0.7      # テンプレートマッチ閾値
  cooldown_seconds: 10      # 電撃後のクールダウン
  # 監視領域（ゲーム解像度に合わせて調整）
  watch_region:
    x: 0
    y: 830
    width: 200
    height: 130

display:
  resolution: "1920x1080"   # ゲームの解像度
```

## calibrate.py の仕様
- スクリーンショットを撮って左下領域を保存
- ユーザーが監視座標を確認・調整できるツール

## requirements.txt
```
mss
opencv-python
numpy
requests
pyyaml
pillow
```

## README.md
- セットアップ方法
- Windows起動時の自動起動設定（タスクスケジューラ）
- キャリブレーション方法

## 注意事項
- Windowsで動かすスクリプト
- タスクスケジューラでログイン時に自動起動
- `pythonw.exe` で実行するとコンソールが出ない（バックグラウンド動作）
