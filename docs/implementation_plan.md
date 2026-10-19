# FPGAお勉強アプリ 実装計画書

管理：実装担当 / 最終更新：2026-10-19

---

## 1. 全体方針

- **最初のリリース（本ドキュメントの対象）**: 第1〜7章の全教材を実装する。第8章・ミニ課題・実機ボード対応は次リリース以降（仕様書§8確定）。
- **現在の状態**: 第1〜7章の骨格と教材（下書き〜レビュー済み）が実装済み。

---

## 2. 章ごとの実装ステップ

| 章 | タイトル | 状態 | 備考 |
|----|---------|------|------|
| 第1章 | 2進数・16進数とビット | ✅ reviewed | lesson01〜03、クイズ・演習あり |
| 第2章 | 論理ゲートと真理値表 | 🔄 draft | lesson01〜03、回路パズル・演習あり |
| 第3章 | 組み合わせ回路 | 🔄 draft | lesson01〜03、演習・回路パズルあり |
| 第4章 | 順序回路 | ✅ reviewed | lesson01〜03、演習・順序回路パズルあり |
| 第5章 | ステートマシン | ✅ reviewed | lesson01〜03、演習あり |
| 第6章 | HDL入門（SystemVerilog） | 🔄 draft | deltasim CLI連携・HDL演習あり |
| 第7章 | シミュレーションと波形 | 🔄 draft | deltasim CLI連携・波形ビューアあり |
| 第8章 | FPGAとは何か | 対象外 | 次リリース以降（仕様書§8） |

> **注**: 第1〜7章が最初のリリース対象（仕様書§8確定）。第8章・ミニ課題・実機ボード対応は次リリース以降。

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
status: draft                # draft | review | reviewed | published（decisions 1）
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
estimated_min: 10             # 目安学習時間（分）
status: draft                 # 下記参照
has_puzzle: false             # 省略時 false（puzzle.yaml がある場合 true）
has_exercise: false           # 省略時 false（exercise.yaml に fill_number/fill_text 等の通常問題がある場合 true）
has_hdl_exercise: false       # 省略時 false（exercise.yaml の type: hdl の HDL演習がある場合 true）
                              # ※ HDL演習のみのレッスンは has_exercise: false, has_hdl_exercise: true
```

**statusフィールドの値（decisions 1）**:

| 値 | 意味 |
|----|------|
| `draft`    | 下書き。教材担当が確認前の状態 |
| `review`   | 確認依頼中。仕様考案係によるレビュー待ち |
| `reviewed` | 仕様考案係が確認済み。リリース候補 |
| `published`| リリース済み。利用者に公開中 |

> **注**: `quiz.yaml` / `puzzle.yaml` の `status` フィールドは廃止（decisions 1）。状態管理は `meta.yaml` のみで行う。

### 3.4 クイズ定義 (quiz.yaml)

```yaml
# status フィールドは廃止（decisions 1）。meta.yaml で管理する。
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
# status フィールドは廃止（decisions 1）。meta.yaml で管理する。
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
5. 仕様考案係による内容確認後、`status` を `review` → `reviewed` → `published` と更新

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

- **利用するフィールド**: `status` / `cases` / `checks` / `errors` / `summary.elapsed_ms`
  - `cases[].checks`: ケースごとの個別チェック結果（信号名・サイクル・期待値・実測値）
  - `cases[].errors`: ケースごとのエラー詳細（ファイル・行・列・重要度・メッセージ・コード）
- **無視するフィールド**: `elapsed_ms`(非推奨), `seed`, `cancelled`, `log`, `module` 等（将来フィールド含む）
- **`schema_version` チェック**: メジャー番号 `"2"` 以外は非対応メッセージを表示（`schema_version` が `"2"` 以外のメジャーの場合に警告）
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

### 3.7 順序回路パズル定義 (puzzle.yaml, decisions 3)

```yaml
id: puzzle_dff_basic
title: "Dフリップフロップを配線しよう"
type: sequential          # 組み合わせ: combinational（省略時）/ 順序: sequential
inputs:
  - name: D
outputs:
  - name: Q
available_gates:
  - type: DFF             # 順序回路ゲート
    count: 1
target_truth_table:
  - clock: 0              # クロック立ち上がり回数
    inputs: {D: 1}        # 立ち上がり直前の入力値
    outputs: {Q: 0}       # 立ち上がり直後の出力値
  - clock: 1
    inputs: {D: 1}
    outputs: {Q: 1}
```

> **decisions 3 定義**: `inputs` は「クロック立ち上がり直前の値」、`outputs` は「立ち上がり直後の値」。

### 3.8 練習問題定義 (exercise.yaml, decisions 2)

```yaml
id: ex_l01_1
type: practice            # practice | hdl（HDL演習は第6・7章）
problems:
  - id: p1
    type: fill_number      # fill_number | fill_text | sort_items
    question: "3ビットで表せる情報の種類は何通りですか？"
    answer: 8
    hint: "2をN回かけた数です"
    wrong_hint: "ビット数を使って計算してみましょう"
```

### 3.9 HDL演習定義 (exercise.yaml, type: hdl)

第6・7章のHDL演習は `exercise.yaml` の `type: hdl` で定義します。

```yaml
id: ex_and_gate
title: "ANDゲートを assign で実装しよう"
type: hdl
difficulty: 1          # 1=穴埋め1行, 2=部分実装, 3=全部書く
spec_file: spec.yaml   # 採点に使う deltasim 仕様YAML
answer_file: answer.sv # 正解例（deltasim でPASS確認済み）
template: |
  module and_gate(input logic a, b, output logic y);
      assign y = /* ここ */;
  endmodule
hints:
  - "AND 演算子は & です"
```

### 3.10 HDL演習の spec.yaml 書き方

```yaml
version: 1
top: and_gate
clock:
  signal: clk
  period_ns: 10
reset:
  duration_cycles: 2
sim:
  cycles: 20
  seed: 42
cases:
  - name: "11_gives_1"
    inputs:
      - at: 3
        set: {a: 1, b: 1}
    expected:
      - at: 3           # 組み合わせ回路は同サイクルで確認
        check: {y: 1}
```

**spec.yaml 設計の原則**:
1. 全入力パターンを網羅する（例: MUX は 2^3=8 ケース）
2. 同サイクルでの set と check を含める
3. リセット優先確認を含める（順序回路）
4. `wrong_codes/manifest.yaml` で FAIL を確認する

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
| YAMLスキーマ検証 | `tests/test_content.py` | 正常・異常系のスキーマ検証（meta/quiz/puzzle/exercise） |
| ゲート評価ロジック | `tests/test_content.py` | AND/OR/NOT/XOR/NAND/NOR/DFF の全真理値表 |
| 回路パズル評価 | `tests/test_puzzle.py` | 正解/不正解/未接続、半加算器、順序回路DFF |
| 進捗保存 | `tests/test_progress.py` | クイズ/パズル/バッジの保存と取得 |
| API エンドポイント | `tests/test_api.py` | 全主要エンドポイントの正常・異常系 |
| deltasim パーサ | `tests/test_simulator.py` | schema_version "2"、cases[]、E_NO_CASE、バージョン互換 |
| HDL演習実機確認 | `tests/test_hdl_integration.py` | answer.svがPASS・wrong_codesがFAIL（deltasimインストール時のみ） |

#### HDL演習の間違いコード検出

各演習に `wrong_codes/` ディレクトリを設置し、「正解例はPASS、間違いコードはFAIL」を統合テストで確認：

| 演習 | 検出可能な誤り | 検出方法 |
|------|--------------|---------|
| Ch6 L2 MUX | sel^a、a\|(sel&b) | 全8組み合わせケースで検出 |
| Ch6 L3 D-FF | リセットなし | 動作中リセットケースで検出 |
| Ch7 L2 カウンタ | 飽和版、0-9版、リセットなし | オーバーフロー＋動作中リセットで検出 |

⚠️ **deltasim 整数サイクル制約（既知の制限、リリース1では許容）**: `assign q=rst?0:d`（組み合わせ回路）や非同期リセット（`always_ff @(posedge clk or posedge rst)`）は、クロックエッジ境界での入力変化のみでは同期DFFと区別できない。各 wrong_codes/manifest.yaml に `expected: PASS_KNOWN_LIMITATION` として明記し、README.md に理由を記載。

#### 既知制約の詳細

| ファイル | 章 | 誤りの内容 | 制約の理由 |
|---------|-----|-----------|-----------|
| Ch06 L3 combinational.sv | 6章 L3 | `assign q = rst?0:d` | クロックエッジ境界での等価動作 |
| Ch06 L3 async_reset.sv | 6章 L3 | `@(posedge clk or posedge rst)` | rst がクロックと同時変化 |
| Ch06 L3 registered_comb.sv | 6章 L3 | `assign d_comb = ...; always_ff q <= d_comb;` | 正しいコードと機能的に等価 |
| Ch07 L2 async_reset.sv | 7章 L2 | 同上（カウンタ版） | 同上 |

**対応予定**: deltasim がサブサイクル刺激（クロックエッジ間の信号変化指定）に対応した時点で、統合テストは PASS_KNOWN_LIMITATION のアサートが壊れるため、その時点で manifest.yaml を `FAIL` に更新する。

CI は GitHub Actions で Linux + Windows の両方で実行する（`.github/workflows/ci.yml`）。

---

## 7. 未対応事項（次にやるべきこと）

1. **HDL演習機能のUI実装**: `fpga_study/server.py` にHDL提出エンドポイントを追加、フロントエンドで採点結果・VCD波形を表示する
2. **教材レビューフロー整備**: `status: review` → `reviewed` → `published` のワークフロー
3. **deltasim PASS_KNOWN_LIMITATION の解消**: deltasim がサブサイクル刺激に対応次第、wrong_codes の manifest.yaml を更新する
5. **LLMヒント機能（任意）**: 「なぜ動かないの？」に答えるローカルLLM連携
6. **実機ボード対応**: 仕様考案係との調整後に対応
