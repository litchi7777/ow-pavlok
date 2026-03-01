# OW Death Detector

Overwatch 2のデス状態をスクリーンキャプチャで検知して、Pavlok APIで電撃するWindowsアプリです。

## 機能

- 画面左下のヒーローポートレートがドクロアイコンに変わったらデス判定
- OpenCVのテンプレートマッチングで検知
- デス検知時にPavlok APIで電撃
- クールダウン機能（連続電撃防止）

## セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. Pavlokトークンの取得

1. Pavlokアプリにログイン
2. https://app.pavlok.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=token にアクセス
3. 認可後、URLから`access_token`を取得

### 3. 設定ファイルの編集

`config.yaml`を編集してPavlokトークンと設定を入力:

```yaml
pavlok:
  access_token: "YOUR_TOKEN_HERE"  # ← ここにトークンを入力
  zap_intensity: 30                 # 電撃強度（1-255）

monitor:
  fps: 2                    # キャプチャ頻度（秒間）
  match_threshold: 0.7      # テンプレートマッチ閾値
  cooldown_seconds: 10      # 電撃後のクールダウン（秒）
  watch_region:
    x: 0
    y: 830
    width: 200
    height: 130
```

### 4. キャリブレーション

監視領域が正しく設定されているか確認:

```bash
python calibrate.py
```

- Overwatchのゲーム画面を表示した状態で実行
- `bottom_left_region_YYYYMMDD_HHMMSS.png`が保存される
- テンプレートマッチングの結果が表示される
- 必要に応じて`config.yaml`の座標を調整

## 使い方

### 手動起動

```bash
python detector.py
```

### バックグラウンド起動（コンソールなし）

```bash
pythonw detector.py
```

### 停止

`Ctrl+C`で停止

## Windows起動時の自動起動設定

### タスクスケジューラで設定

1. タスクスケジューラを起動（`Win+R` → `taskschd.msc`）
2. 「基本タスクの作成」をクリック
3. 名前: `OW Death Detector`
4. トリガー: `ログオン時`
5. 操作: `プログラムの開始`
6. プログラム/スクリプト: `C:\Python39\pythonw.exe`（Pythonのパス）
7. 引数の追加: `C:\path\to\ow-death-detector\detector.py`（スクリプトのパス）
8. 開始: `C:\path\to\ow-death-detector`（作業ディレクトリ）

### バッチファイルで起動

`start_detector.bat`を作成:

```bat
@echo off
cd /d "%~dp0"
pythonw detector.py
```

このバッチファイルをスタートアップフォルダに配置:
- `Win+R` → `shell:startup`

## トラブルシューティング

### デス状態が検知されない

1. `calibrate.py`で監視領域を確認
2. `config.yaml`の`match_threshold`を下げる（0.6など）
3. `config.yaml`の`watch_region`座標を調整

### Pavlok APIエラー

- トークンが正しいか確認
- ネットワーク接続を確認
- Pavlokデバイスがペアリングされているか確認

### 動作が重い

- `config.yaml`の`fps`を下げる（1など）
- `watch_region`のサイズを小さくする

## ファイル構成

```
ow-death-detector/
├── README.md                # このファイル
├── detector.py              # メイン監視スクリプト
├── config.yaml              # 設定ファイル
├── calibrate.py             # キャリブレーションツール
├── requirements.txt         # 依存パッケージ
├── skull_template.png       # ドクロアイコンのテンプレート
├── death_screen_sample.png  # サンプル画像
└── bottom_left_region.png   # キャリブレーション用画像
```

## 注意事項

- このツールはWindows専用です
- ゲーム解像度が1920x1080以外の場合は`config.yaml`を調整してください
- 電撃強度は適切に設定してください（推奨: 30-50）
- Overwatchの利用規約に従ってご使用ください
