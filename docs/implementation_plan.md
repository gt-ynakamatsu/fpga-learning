# FPGAお勉強アプリ 実装計画書

管理：実装担当 / 最終更新：2026-10-19

---

## 1. 全体方針

- **最初のリリース（本ドキュメントの対象）**: 第1〜7章の骨格＋第1・2章の教材を実装する。第8章・ミニ課題・実機ボード対応は次リリース以降。
- **今回の実行で完成させる範囲**: 骨格 + 第1章（全3レッスン）+ 第2章（回路パズル含む全3レッスン）
- 第3〜7章は次の実行で追加する。

---

## 2. 章ごとの実装ステップ

| 章 | タイトル | 状態 | 備考 |
|----|---------|------|------|
| 第1章 | 2進数・16進数とビット | ✅ 実装済み（下書き） | lesson01〜03、クイズあり |
| 第2章 | 論理ゲートと真理値表 | ✅ 実装済み（下書き） | lesson01〜03、回路パズルあり |
| 第3章 | 組み合わせ回路 | 🔲 次リリース | 加算器・マルチプレクサ等 |
| 第4章 | 順序回路 | 🔲 次リリース | FF・カウンタ等 |
| 第5章 | ステートマシン | 🔲 次リリース | |
| 第6章 | HDL入門（SystemVerilog） | 🔲 次リリース | deltasim CLIが必要 |
| 第7章 | シミュレーションと波形 | 🔲 次リリース | deltasim CLIが必要 |
| 第8章 | FPGAとは何か | 対象外 | 次リリース以降 |

---

## 3. 教材ファイルフォーマット

### 3.1 ディレクトリ構造

```
fpga_study/data/
├── chapter01/
│   ├── meta.yaml           # 章メタデータ
│   ├── lesson01/
│   │   ├── meta.yaml       # レッスンメタデータ
│   │   ├── content.md      # 本文（Markdown）
│   │   └── quiz.yaml       # クイズ問題
│   └── ...
└── chapter02/
    └── lesson03/
        ├── puzzle.yaml     # 回路パズル定義
        └── ...
```

### 3.2 章メタデータ (meta.yaml)

```yaml
id: chapter01
title: "2進数・16進数とビット"
description: "..."
order: 1                     # 表示順（1始まり）
status: draft                # draft | review | published
lessons:
  - lesson01
  - lesson02
  - lesson03
```

### 3.3 レッスンメタデータ (meta.yaml)

```yaml
id: lesson01
title: "デジタルの世界と「ビット」"
description: "..."
estimated_min: 10            # 目安学習時間（分）
status: draft                # draft | review | published
has_puzzle: false            # 回路パズルがある場合 true
```

**statusフィールドの意味:**
- `draft`: 下書き。教材担当が確認前の状態
- `review`: レビュー中。仕様考案係による確認中
- `published`: 公開済み

### 3.4 クイズ定義 (quiz.yaml)

```yaml
status: draft
questions:
  - id: q1
    question: "問題文"
    options:
      - "選択肢A"
      - "選択肢B"
      - "選択肢C"
      - "選択肢D"
    answer: 0              # 正解の選択肢インデックス（0始まり）
    explanation: "解説文"
```

### 3.5 回路パズル定義 (puzzle.yaml)

```yaml
id: puzzle_and_gate
title: "パズルのタイトル"
description: "説明文"
status: draft
inputs:
  - name: A
  - name: B
outputs:
  - name: Y
available_gates:
  - type: AND       # AND | OR | NOT | XOR | NAND | NOR
    count: 1        # 使える最大数
target_truth_table:
  - inputs: {A: 0, B: 0}
    outputs: {Y: 0}
  - inputs: {A: 1, B: 1}
    outputs: {Y: 1}
```

### 3.6 教材追加手順

1. `fpga_study/data/` に章ディレクトリを追加
2. `meta.yaml`（章）を記述（`status: draft` を忘れずに）
3. レッスンディレクトリを追加し、`meta.yaml`・`content.md`・`quiz.yaml` を記述
4. サーバーを再起動（コードは修正不要）
5. 仕様考案係による内容確認後、`status` を `review` → `published` に変更

---

## 4. deltasim CLI 連携方針

### 4.1 呼び出し形式 (docs/api.md §2.2 準拠)

```bash
deltasim test <RTLファイル...> --spec <仕様YAML> --json <出力パス>
```

- `--json` はファイルパス（stdoutではない）
- オプション: `--top <モジュール名>` `--seed <整数>`
- 進捗: `--json-events` でJSON Lines をstdoutへ（現バージョンは未使用）

### 4.2 出力JSONの読み取り方針

- **利用するフィールド**: `status` / `checks` / `errors` のみ
- **無視するフィールド**: `elapsed_ms`, `seed`, `cancelled`, `log`, `module` 等（将来フィールド含む）
- **`schema_version` チェック**: `"1"` 以外は非対応メッセージを表示して終了
- **パーサの一元化**: `fpga_study/simulator.py` の `_parse_deltasim_result()` に集約。フォーマット変更時はここだけ修正する

### 4.3 近日変更予定への対応

docs/api.md「未決事項」より:
- テストケース単位の集計フィールド追加 → 未知フィールドは無視するので自動対応
- `summary.elapsed_ms` 追加 → 同上
- `"z"` 値を `"x"` と区別 → 4値文字列(0/1/x/z)のまま保持するだけなので対応不要

### 4.4 未インストール環境での動作

deltasim がインストールされていない場合:
- `DeltasimCLISimulator.is_available()` が `False` を返す
- `get_default_simulator()` が `StubSimulator` を返す
- 初心者向けメッセージ: 「HDLシミュレータ (deltasim) がインストールされていません。インストール方法: pip install deltasim」

### 4.5 将来の拡張ポイント

```
Simulator (Protocol)
├── StubSimulator         # 現在: 開発/未インストール用
├── DeltasimCLISimulator  # 現在: CLI連携（deltasim test --json）
├── DeltasimPythonAPISimulator  # 将来: Python API (ds.test()) 直接呼び出し
└── BoardSimulator        # 将来: 実機ボード対応
```

`fpga_study/simulator.py` の `get_default_simulator()` を変更するだけで切り替え可能。

---

## 5. アーキテクチャ概要

```
fpga_study/
├── cli.py          # エントリポイント (fpga-study コマンド)
├── server.py       # FastAPI アプリ (REST API + 静的ファイル配信)
├── progress.py     # SQLite による進捗・バッジ管理
├── simulator.py    # Simulator プロトコル + deltasim CLI 連携
├── content/
│   ├── loader.py   # Markdown/YAML 読み込み・回路評価
│   └── validator.py  # JSONSchema による YAML 検証
├── static/
│   ├── index.html  # SPA のシェル
│   ├── style.css   # スタイル（外部CDN不使用）
│   ├── app.js      # SPA ルーター + 各画面の UI ロジック
│   └── puzzle.js   # SVGベース回路パズルエディタ
└── data/           # 教材ファイル（Markdown + YAML）
```

---

## 6. テスト方針

| テスト対象 | ファイル | 内容 |
|-----------|---------|------|
| YAMLスキーマ検証 | `tests/test_content.py` | 正常・異常系のスキーマ検証 |
| ゲート評価ロジック | `tests/test_content.py` | AND/OR/NOT/XOR/NAND/NOR の全真理値表 |
| 回路パズル評価 | `tests/test_puzzle.py` | 正解/不正解/未接続の各パターン |
| 進捗保存 | `tests/test_progress.py` | クイズ/パズル/バッジの保存と取得 |
| API エンドポイント | `tests/test_api.py` | 全主要エンドポイントの正常・異常系 |
| deltasim パーサ | `tests/test_simulator.py` | docs/api.md サンプルJSONを使った検証、堅牢性テスト |

CI は GitHub Actions で Linux + Windows の両方で実行する（`.github/workflows/ci.yml`）。

---

## 7. 未対応事項（次にやるべきこと）

1. **第3〜7章の教材作成**: 組み合わせ回路・順序回路・ステートマシン・HDL・シミュレーション
2. **HDL演習機能の実装**: `fpga_study/server.py` にHDL提出エンドポイントを追加、`DeltasimCLISimulator.run()` を実際の教材フローに組み込む
3. **deltasim の仕様YAML形式**: 教材ごとにどのような `spec.yaml` を用意するか設計が必要
4. **教材レビューフロー**: `status: review` になったファイルを仕様考案係が確認するワークフロー整備
5. **LLMヒント機能（任意）**: 「なぜ動かないの？」に答えるローカルLLM連携
6. **実機ボード対応**: 仕様考案係との調整後に対応
