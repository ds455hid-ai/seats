# AI写真・動画整理システム(Phase 1 MVP)

大量の写真・動画をユーザーが1枚ずつ確認せずに整理するためのシステムです。
**すべてローカル処理・無料構成**で、有料AI APIは一切使用していません。

外部送信は一切行いません。解析はすべてPC(あなたのMac/Windows)上、確認・削除実行はすべてiPhone上で完結します。

## 全体の流れ

```
iPhoneの写真・動画をSSD/USBへコピー
   ↓
PC側解析アプリ(FastAPI + Python)で自動解析
   ↓
重複・類似・削除候補を自動分類してWebブラウザで確認
   ↓
delete_manifest.json を生成
   ↓
USB/SSD経由でiPhoneのFilesアプリへコピー
   ↓
iPhoneアプリ(SwiftUI + PhotoKit)がPHAssetと照合(MATCHED/AMBIGUOUS/NOT_FOUND)
   ↓
本人が最終確認(バックアップ確認含む)
   ↓
PhotoKitの正式APIで削除実行
```

**重要な安全方針**: どれだけ削除候補スコアが高くても、システムが自動的に削除することは一切ありません。
必ず人間が確認・確定した項目だけが削除されます。iPhone側では、少しでも照合に確信が持てない
(AMBIGUOUS)場合や見つからない(NOT_FOUND)場合は、自動的に削除対象から除外されます。

---

## ディレクトリ構成

```
photo-organizer/
  pc-app/              PC側解析アプリ(Python/FastAPI)
    app/               解析ロジック・API本体
    web/               Webフロントエンド(Jinja2 + Vanilla JS、npm不要)
    config/            スコアリングルール・設定ファイル(YAML)
    tests/             pytestテスト
  iphone-app/          iPhone側アプリ(Swift)
    PhotoOrganizerCore/  照合ロジック等の純粋なSwiftコード(PhotoKit非依存、単体テスト可能)
    PhotoOrganizerApp/   SwiftUI + PhotoKitのアプリ本体(要Xcode)
```

---

## 1. PC側解析アプリのセットアップ(macOS想定、Windows対応可能な設計)

### 必要なソフトのインストール

**Python 3.11以上** と **ffmpeg** が必要です。まだ入っていない場合は以下を実行してください。

```bash
# Homebrewが入っていない場合は先にインストール(https://brew.sh を参照)
brew install python@3.11 ffmpeg
```

### セットアップコマンド(コピー&ペーストで実行できます)

```bash
cd photo-organizer/pc-app
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp config/settings.example.yaml config/settings.yaml
```

### サーバーの起動

```bash
cd photo-organizer/pc-app
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

起動したら、ブラウザで **http://127.0.0.1:8000** を開いてください。このサーバーは
`127.0.0.1`(自分のPCの中だけ)で動作し、外部からはアクセスできません。

### 使い方

1. ダッシュボード画面で、解析したいフォルダの絶対パス(例: `/Volumes/BackupSSD/DCIM`)を入力し「解析開始」を押す
2. 解析が終わると、重複・類似写真・スクリーンショット・ピンぼけ・大容量動画などがカテゴリ別に表示される
3. 「類似写真」画面でグループごとに残す1枚を確認・変更する
4. 「削除予定」画面で最終的な削除候補を確認し、除外したいものは「残す」にする
5. 「delete_manifest.json を生成」を押すと確定し、ファイルが `pc-app/data/exports/` に保存される
6. そのファイルをUSBメモリ等でiPhoneのFilesアプリにコピーする

### テストの実行

```bash
cd photo-organizer/pc-app
source .venv/bin/activate
pytest -v
```

53件のテストがあり、重複判定・類似判定・スコアリング・manifest生成・動画メタデータ・
誤削除防止(異なる写真を誤って重複/類似と判定しないこと)を検証しています。全件パス済みです。

---

## 2. iPhone側アプリのセットアップ(要Xcode、macOS上でのみ可能)

iPhone側はPhotoKit(Appleの正式な写真ライブラリAPI)を使うため、**Xcode(macOS専用)でのみ**
ビルド・実行できます。このリポジトリにはXcodeプロジェクトファイル(.xcodeproj)そのものは
含めていません(バイナリ形式のプロジェクトファイルを自動生成するとXcodeバージョン差異で
壊れるリスクが高いため)。以下の手順でXcode上に新規プロジェクトを作り、ソースファイルを
追加してください。

### 手順

1. Xcodeで **File → New → Project → iOS → App** を選択し、「PhotoOrganizerApp」という名前で作成
   (Interface: SwiftUI、Language: Swift)
2. **File → Add Package Dependencies → Add Local...** で `iphone-app/PhotoOrganizerCore` フォルダを選択し、
   ローカルSwift Packageとして追加する
3. `iphone-app/PhotoOrganizerApp/` 以下のSwiftファイルをすべてXcodeプロジェクトにドラッグ&ドロップで追加する
4. `iphone-app/PhotoOrganizerApp/Info.plist` の内容(`NSPhotoLibraryUsageDescription`)を、
   プロジェクトの Info タブ(またはInfo.plist)にコピーする
5. 実機(iPhone)またはシミュレータを選択してビルド・実行する

### PhotoOrganizerCoreの単体テスト実行

`PhotoOrganizerCore` は PhotoKit に依存しない純粋なSwiftコードなので、Xcode不要で
コマンドラインからテストできます(Swiftツールチェインがインストールされている環境の場合):

```bash
cd photo-organizer/iphone-app/PhotoOrganizerCore
swift test
```

Xcode上であれば、`PhotoOrganizerCore`パッケージを開いて `Cmd+U` でも実行できます。

テスト対象: delete_manifest.jsonのパース、そして最も重要な **PHAsset照合ロジック
(AssetMatcher)の誤削除防止テスト** — 撮影日時だけが同じ、ファイル名だけが同じ、
ファイルサイズが近いだけ、といった「単一要素の一致だけでは絶対にMATCHEDにしない」ことを
検証しています。

> **注記**: この開発環境にはmacOS/Xcode/Swiftツールチェインが無いため、iPhone側のSwiftコードは
> このセッション内では実際にコンパイル・実行確認ができていません。文法は慎重にレビューしましたが、
> 実機での動作確認はXcode環境で行ってください。もし何かエラーが出た場合はその内容を教えてください。

### 使い方

1. 初回起動時に写真ライブラリへのアクセスを許可(フルアクセス推奨)
2. PC側で生成した `delete_manifest.json` をFilesアプリ経由で選択して読み込む
3. 自動的にPHAssetとの照合が行われ、MATCHED/AMBIGUOUS/NOT_FOUNDに分類される
4. MATCHEDの項目だけがチェックボックスで選択可能。不要なものはチェックを外して除外できる
5. 「確認画面へ進む」→ バックアップ済みか確認 → 「削除を実行」で確定
6. 削除後、「最近削除した項目」を確認して完全に容量を空けられることを案内

---

## 無料版と有料版の違い

| 機能 | 無料版(Phase 1、本リポジトリ) | 有料クラウドAPIを使った場合 |
|---|---|---|
| 完全重複検出 | ○ (SHA-256) | 同等 |
| 類似写真検出 | ○ (pHash/dHash) | より高精度な埋め込みベクトル比較が可能 |
| ピンぼけ・明るさ判定 | ○ (OpenCV Laplacian分散等) | 同等〜やや高精度 |
| スクリーンショット判定 | △ 推定(ヒューリスティック) | 高精度 |
| 顔検出・目つむり判定 | Phase2でMediaPipe等を追加予定、精度は「推定」表示 | Vision APIなら高精度 |
| 意味分類(家族・旅行・料理等) | Phase2でローカルCLIPを追加可能(PCスペックに応じてON/OFF) | 高精度、多言語対応 |
| 日本語OCR(レシート等) | Tesseract/Apple Vision(オンデバイス)、精度は限定的 | 高精度 |

---

## Phase構成

- **Phase 1(本リポジトリで実装済み)**: 重複/類似検出、画質判定、スクショ/画面録画推定、
  削除候補スコア、Web UI、iPhone連携・PhotoKit削除
- **Phase 2(未実装、拡張ポイントは用意済み)**: ローカルCLIPによる意味分類
  (`analysis_results`テーブルに任意の分類結果を保存できる構造にしてあります)
- **Phase 3(未実装)**: 自然言語による整理条件指定

---

## セキュリティ・プライバシー方針

- 写真・動画そのものやその内容は外部のいかなるサーバーにも送信しません
- PC側Webサーバーは `127.0.0.1` のみでリッスンし、ローカルネットワーク外からはアクセスできません
- 操作ログには件数・日時のみを記録し、ファイルパスや画像内容は記録しません
- サムネイルキャッシュは設定画面からいつでも削除できます
- iPhone側アプリの操作ログもファイルパス等は含みません
