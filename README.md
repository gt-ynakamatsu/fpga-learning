# FPGAお勉強アプリ

完全な初心者向けのFPGA学習ウェブアプリです。  
2進数・論理ゲートの基礎から、回路パズル、HDL演習まで段階的に学べます。

---

## 必要な環境

- Python 3.10 以上
- Windows または Linux（macOS でも動作します）
- インターネット接続不要（完全オフライン動作）

---

## インストール

```bash
pip install .
```

開発用（テスト含む）:

```bash
pip install ".[dev]"
```

---

## 起動方法

```bash
fpga-study
```

ブラウザが自動で開きます（`http://127.0.0.1:8731`）。

### オプション

```bash
fpga-study --port 9000      # ポート番号を変えたいとき
fpga-study --no-browser     # ブラウザを自動で開かない
fpga-study --reload         # 開発用：コード変更時に自動リロード
fpga-study --show-drafts    # 開発用：draft/review 状態のレッスンも表示する
```

---

## 演習の使い方

1. **起動** → ブラウザで `http://127.0.0.1:8731` を開く
2. **章を選ぶ** → カリキュラムから好きな章をクリック
3. **レッスンを選ぶ** → レッスン一覧から選択
4. **学習フロー**: 説明を読む → ✏️ 練習問題を解く → 📝 確認クイズ
   - **練習問題**: 数値や文字を入力して「確認」ボタンで答え合わせ
   - **HDL 演習**（第6・7章）: コードを入力して「▶ 実行して採点」
5. **回路パズル**（第2〜4章）: ゲートをドラッグして配線し「⚡ 回路を確認」で判定

---

## テストの実行

```bash
# 全テストを実行
pytest

# カバレッジ付き
pytest --cov=fpga_study --cov-report=term-missing

# 特定のファイルだけ実行
pytest tests/test_puzzle.py -v
```

---

## 教材の追加方法

教材は `fpga_study/data/` 以下の Markdown + YAML ファイルで管理しています。  
ファイルを追加するだけで、サーバー再起動後に新しいレッスンが表示されます。

### 新しいレッスンを追加する手順

1. **章ディレクトリを作成**:

```
fpga_study/data/chapter03/
├── meta.yaml
├── lesson01/
│   ├── meta.yaml
│   ├── content.md
│   └── quiz.yaml
└── lesson02/
    ├── meta.yaml
    ├── content.md
    ├── quiz.yaml
    └── puzzle.yaml   ← 回路パズルがある場合のみ
```

2. **章メタデータ (`meta.yaml`)** を記述:

```yaml
id: chapter03
title: "組み合わせ回路"
description: "加算器・マルチプレクサを作ろう"
order: 3
status: draft
lessons:
  - lesson01
  - lesson02
```

3. **レッスンメタデータ (`lessonXX/meta.yaml`)** を記述:

```yaml
id: lesson01
title: "半加算器を作ろう"
description: "1ビットの足し算回路を設計する"
estimated_min: 15
status: draft
```

4. **本文 (`content.md`)** を Markdown で書く。

5. **クイズ (`quiz.yaml`)** を定義:

```yaml
status: draft
questions:
  - id: q1
    question: "半加算器の入力は何ビットですか？"
    options:
      - "1ビット"
      - "2ビット"
      - "4ビット"
      - "8ビット"
    answer: 1
    explanation: "半加算器はAとBの2ビットを入力として受け取ります。"
```

6. **回路パズル (`puzzle.yaml`)** を定義（省略可）:

```yaml
id: puzzle_half_adder
title: "半加算器を作ろう"
description: "SUM と CARRY を出力する半加算器を作ってください"
status: draft
inputs:
  - name: A
  - name: B
outputs:
  - name: SUM
  - name: CARRY
available_gates:
  - type: XOR
    count: 1
  - type: AND
    count: 1
target_truth_table:
  - inputs: {A: 0, B: 0}
    outputs: {SUM: 0, CARRY: 0}
  - inputs: {A: 0, B: 1}
    outputs: {SUM: 1, CARRY: 0}
  - inputs: {A: 1, B: 0}
    outputs: {SUM: 1, CARRY: 0}
  - inputs: {A: 1, B: 1}
    outputs: {SUM: 0, CARRY: 1}
```

7. サーバーを再起動すると新しいレッスンが表示されます。

---

## status フィールドについて

教材の YAML には `status` フィールドがあります：

| 値 | 意味 |
|----|------|
| `draft` | 下書き（未レビュー）。アプリに「📝 下書き」バッジが表示される |
| `review` | レビュー中。仕様考案係による確認中 |
| `published` | 公開済み。バッジは非表示 |

---

## プロジェクト構成

```
fpga_study/
├── cli.py          # fpga-study コマンドのエントリポイント
├── server.py       # FastAPI アプリ（REST API）
├── progress.py     # 学習進捗の保存（SQLite, ~/.fpga_study/progress.db）
├── simulator.py    # シミュレータ抽象インターフェース（deltasim CLI 連携）
├── content/
│   ├── loader.py   # 教材の読み込みと回路評価ロジック
│   └── validator.py  # YAMLスキーマ検証
├── static/         # フロントエンド（HTML/CSS/JS、外部CDN不使用）
└── data/           # 教材ファイル
    ├── chapter01/  # 第1章: 2進数・16進数とビット
    └── chapter02/  # 第2章: 論理ゲートと真理値表
docs/
└── implementation_plan.md  # 実装計画書
tests/              # ユニットテスト・APIテスト
```

---

## 学習データの保存場所

進捗データは `~/.fpga_study/progress.db`（SQLite）に保存されます。  
外部への送信は一切行いません。

---

## HDLシミュレーション（第6・7章）

第6・7章のHDL演習には **deltasim 0.2.2 以上** が必要です。

```bash
# v0.2.2 タグ公開後（推奨）:
pip install 'git+https://github.com/gt-ynakamatsu/deltasim.git@v0.2.2'

pip install 'git+https://github.com/gt-ynakamatsu/deltasim.git@v0.2.2'
```

deltasim がインストールされていない場合、第1〜5章の回路パズルは引き続き利用できます。

### 開発オプション

```bash
fpga-study --show-drafts   # draft/review 状態のレッスンも表示
```

---

## ライセンス

MIT License
