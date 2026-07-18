# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

3D パスに沿って **1 本の鉄筋** を配置するシンプルな VectorWorks **プラグインオブジェクト（PIO）** スクリプトです。姉妹プロジェクト `vectorworks-plugin-rebar`（配筋）と同じアーキテクチャ・コーディング規約・実行時自動更新の仕組みを踏襲しています。

PIO は 3D パス図形 `鉄筋` として VectorWorks に登録され（README の登録手順参照）、3D パス＝鉄筋の芯線、呼び径（`D13` 等）を保持する。出力は 3 系統:

1. **本体（3D）**: 鉄筋径（最外径）の円形断面をパスに沿って押し出した丸鋼のソリッド（`vs.CreateExtrudeAlongPath`）。生成に失敗する環境では 3D ポリライン（芯線）へフォールバックする。
2. **平面（Top/Plan）**: 上から見たパスの投影図（面内の鉄筋＝2D 線）と、呼び径の**2D 表示記号**（縦筋のように上から見ると点になる鉄筋を ●／× で示す）。2D 記号は、パスが `CutHeight` パラメータで指定した**切断高さ（z）を横切る XY 位置**に描く（パスが折り返して複数回横切れば記号も複数、横切らなければ描かない、切断面に載る水平区間は 2D 線で出るので描かない。`CutHeight` 無指定なら既定で z 範囲の中央で切る）。ハイブリッド図形は Top/Plan で 2D regen を表示するため、3D の端部投影（カギ状）ではなくこのクリーンな 2D 記号が出る。平面の 2D 記号・投影線は PIO 本体クラス。
3. **断面記号（3D）**: 呼び径に応じた表示記号（●／× 等、配筋標準図 KSE 2008「鉄筋の表示記号」）の**断面形状（線画）**をパスに沿って押し出した図形。線・輪郭円は**開いた曲線を押し出した面**（切断すると**線**として出る＝細い ×・輪郭の ○）、塗り円 ● だけは塗り円を押し出したソリッド（切断すると塗り円）。断面ビューポートはこれらを**ネイティブに切断**するため、折れ・フック・斜め配置でも、どの位置で切っても正しい位置に記号が出る。

**2D コンポーネントは使わない。** 以前は断面表現に `Set2DComponentGroup`（2D コンポーネント）を使っていたが、(a) オブジェクトのローカル 6 軸・紙面平面という制約で斜め配筋を扱えない、(b) 紙面座標系の原点が PIO のローカル原点（パス第 1 頂点）で、本体の描画位置とずれる、という問題があった。実体のソリッドをネイティブに切断する方式に変更し、位置ずれと斜め配筋の両方を根本的に解消した。

本体（丸鋼）と平面線は **PIO 本体の描画クラス**（`vs.GetClass(pio)`）に割り当てる。**断面記号ソリッドだけは別のクラス**（`SymbolClass` パラメータで指定）に割り当てる。ビューポートごとのクラス表示で、3D ビューでは記号クラスを非表示（丸鋼を表示）、断面ビューポートでは本体クラスを非表示（記号を表示）と切り替える運用（README 参照）。作図クラスは命令セットには含めない（クラス管理は描画フェーズ＝PIO を扱う側）。`SymbolClass` のクラス名だけは params から描画フェーズへ直接渡す。

## 配筋（vectorworks-plugin-rebar）との関係

姉妹プロジェクト「配筋」PIO が、この「鉄筋」PIO を 3D パスで多数配置して配筋全体を組み立てる 2 段階構成の下位オブジェクト。1 本ごとを独立した鉄筋オブジェクト（実体のある 3D ソリッド）にすることで、断面ビューポートが各鉄筋を個別に切断でき、単一の配筋オブジェクトが多方向の鉄筋を 1 つの 2D コンポーネントで表現していたときの制約（斜め配筋不可・切断位置に関係なく全表示）を回避する。**まず本 PIO を VectorWorks 上で検証してから配筋側の改修を行う**方針。

## アーキテクチャ: 2 フェーズ分離

処理は **配筋計算フェーズ** と **VectorWorks 描画フェーズ** に完全分離されている。両フェーズは JSON 直列化可能な**命令セット（ドキュメント）**だけで接続され、`vs` との密結合を避けることで検証や VectorWorks バージョンアップ対応を容易にしている。

1. **配筋計算フェーズ（`rebar` サブパッケージ）** — `vs` に一切依存しない。PIO のパラメータとパス頂点（プレーンな dict）から、描くべき図形を命令セット（dict）として組み立てる。通常の Python 環境で単体実行・検証できる。
2. **描画フェーズ（`vw` サブパッケージ）** — `vs` だけに依存し、鉄筋の知識（呼び径・記号の意味等）を持たない。命令セットを検証（`validate_document`）してから vs API で描画する。

命令セットのスキーマ（version・path/tube_diameter/plan_lines/symbol_profiles の各形式）は `document.py` の docstring に定義されている。`symbol_profiles` は断面（パスに直交する紙面）上の線画（`line`＝線・`circle`＝円 `filled` で塗り/輪郭を切替）で、原点(0,0)中心に組み立てる（押し出しがパスに沿って配置するため位置合わせ不要）。スキーマを変更するときは `DOCUMENT_VERSION` の互換性に注意し、`TypedDict` 定義・docstring・`validate_document()` とテストも併せて更新すること。`run()` は両フェーズの間で `json.dumps`/`json.loads` を通すため、命令セットに直列化不能なオブジェクト（vs ハンドル等）を入れてはならない。

## パッケージ構造

```
src/
    vectorworks_plugin_rebar_single/  # pip インストール可能なパッケージ本体
        __init__.py       # run() を公開 (PIO 読取 → 計算 → JSON 命令セット → 描画)
        document.py       # 命令セットのスキーマ定義・検証 (vs 非依存)
        rebar/            # フェーズ1: 計算 (vs 非依存)
            __init__.py   # build_document(params) -> dict / 既定値定数
            spec.py       # 呼び径パース (D13 / NFKC 正規化) と最外径表
            symbol.py     # 標準図の表示記号 → 断面プロファイル(disk/ring/polygon)
        vw/               # フェーズ2: VectorWorks 描画 (vs 依存)
            __init__.py   # execute_document(document, pio_handle, symbol_class) -> 実行数 dict
            pio.py        # PIO コンテキスト読取 (パラメータ・パス頂点 → params dict)
            draw.py       # 2D 線・3D ソリッド押し出し(本体丸鋼・記号) (by-class 属性)
main.py                  # VectorWorks に登録する PIO スクリプト (実行時に自動インストール・更新)
tests/                   # pytest 用テスト (CI は vs.py スタブを GitHub からダウンロード)
pyproject.toml           # パッケージメタデータ
```

`vs` を import してよいのは `vw` サブパッケージ内・`run()` 関数内・`main.py` の設定フォルダ検出（いずれも関数内の遅延 import）だけ。`rebar` サブパッケージや `document.py` に `vs` への依存を持ち込まないこと。テストもこの分離に従う: `tests/test_rebar_*.py`・`tests/test_document.py` は vs モック不要、`tests/test_vw_*.py`・`tests/test_init.py` は手書きの命令・パラメータを vs モックで実行して検証する。

## コーディング規約: 型注釈

すべての関数・メソッド（テストコード・モック用クロージャ含む）に引数と戻り値の型注釈を付ける。型検査は mypy で行い、CI で `mypy` を実行する（設定は `pyproject.toml` の `[tool.mypy]`、`disallow_untyped_defs` 有効）。

- 各モジュール先頭に `from __future__ import annotations` を置く。Python 3.9 互換を保ちつつ `list[str]` / `X | None` 構文を使うため。
- 命令セットの型は `document.py` の `TypedDict`（`Document` / `PlanLineCommand`）を使う。断面プロファイル（disk/ring/polygon で持つキーが異なる不均質な dict）は `Profile = Dict[str, Any]` とし、実行時検証（`validate_document`）で形を保証する。
- `vs` モジュールは型スタブが存在しないため `ignore_missing_imports` で許容し、vs ハンドルは `Any` で扱う。VectorWorks 公式 `vs.py` スタブ（`tests/vs.py`）は型検査対象から除外している。
- 検証前の命令セット（JSON 由来の信頼できない入力）を受ける関数（`validate_document()` / `execute_document()`）の引数は `Any` とし、検証済みの値だけを `Document` 型として扱う。

## スクリプトの実行方法

このスクリプトは単独の Python プログラムとして動作しません。**VectorWorks 内で PIO のリセットスクリプトとして実行する必要があります**。`vs` モジュールは VectorWorks 独自の Python スクリプト API であり、pip でインストールすることはできません。

テストは VectorWorks の公式 `vs.py` スタブをモック対象として `pytest` で実行します（`.github/workflows/test.yml` 参照）。

## 実行時自動更新（main.py）

配筋（rebar）の main.py と同じ仕組み（GitHub `main` ブランチのコミット SHA 比較 → アーカイブ直接展開 → 依存は pip）。パッケージ名・リポジトリ名だけが異なる。**開発初期は頻繁に変更して試すため、リセットのたびに毎回更新を確認する**。更新した場合はキャッシュ済みモジュールを破棄するため、VectorWorks を再起動しなくても次のリセットから新しいコードが使われる。

## PIO スクリプトの処理フロー

`vectorworks_plugin_rebar_single.run()` は PIO のリセットのたびに以下を行う:

1. **PIO コンテキスト読取（`vw/pio.py`）** — `vs.GetCustomObjectInfo()` で PIO ハンドルを取得し、`vs.GetRField` でパラメータ（`Bar` / `MarkScale` / `SymbolClass`）を、`vs.GetCustomObjectPath` + `vs.GetPolyPt3D`（**0 始まり**インデックス）でパス頂点を読む。数値フィールドは単位付き文字列を許容し、解釈できないフィールドはキーを省いて既定値に委ねる。
2. **計算（フェーズ1）** — `rebar.build_document(params)` で JSON 命令セットを組み立てる。パス頂点は連続重複点の除去（`_clean_path`）に加え、**直線上に並ぶ連続区間を 1 区間へマージ**（`_merge_collinear`）してから使う。1 本の鉄筋は断面形状（呼び径）がパス全体で同一なので、地中梁のように直線上へ小刻みに頂点が並ぶパスでも冗長な中間頂点を除いて 1 つのまっすぐな区間として扱い、平面の投影線が細切れにならない（反対向きの折り返し頂点は残す）。呼び径の形式不正・パス不足は `SpecError`（ユーザー向け日本語メッセージ）。
3. **JSON 経由の受け渡し** — `json.dumps` → `json.loads` を通し直列化可能性を保証。
4. **描画（フェーズ2）** — `vw.execute_document(document, pio_handle, symbol_class)` が検証後、本体丸鋼（PIO クラス）→ 平面線（PIO クラス, regen）→ 断面記号ソリッド（`SymbolClass`）の順で描画する。
5. **エラー表示** — リセットは頻繁に実行されるためモーダルダイアログは使わず、`vs.Message` でステータスバーに表示する（`SpecError` は入力の直し方が分かるメッセージ）。

### 3D ソリッド（vw/draw.py）

- **`vs.CreateExtrudeAlongPath(pathHandle, profileHandle)`** で断面プロファイルをパスに沿って押し出したソリッドを作る。パスは NURBS 曲線（`vs.CreateNurbsCurve` + `vs.AddVertex3D`、次数 1＝折れを丸めない線形補間）。押し出しはパスを消費するため、押し出しごとに新しい NURBS パスを作る。
- **本体丸鋼**: プロファイルは原点中心の円（`vs.Oval`）。生成に失敗する環境（関数が無い VW バージョン・NULL 戻り・例外）では **3D ポリライン（芯線）へフォールバック**する。
- **断面記号**: プロファイルは記号ごとの線画。線・輪郭円は**開いた曲線**を押し出して面にし（切断＝線）、塗り円 ● だけ塗り円を押し出してソリッドにする（切断＝塗り円）。
  - `line`（× ・+ ・斜線）: `vs.MoveTo`/`vs.LineTo` の線を押し出す（開いた線→平面→切断が線）。
  - `circle` `filled=false`（○ 等の輪郭）: `vs.ArcByCenter`（0〜360°）の輪郭円を押し出す（開いた曲線→筒面→切断が輪郭線）。
  - `circle` `filled=true`（● ・中心点）: `vs.Oval` の塗り円を押し出す（閉じた面→ソリッド→切断が塗り円）。
- 記号は押し出しに失敗しても（本体丸鋼と違い）フォールバックせず描かない。
- **開いた曲線の押し出しが断面ビューポートで線として切断表示されるか、プロファイルの向き・原点、記号の紙面上の向き（押し出しの回転フレーム）、左右ビューの見え方は VectorWorks 上で最終確認する**（描画フェーズは VW 上で検証する方針）。

### 描画の規約（vw/draw.py）

- 2D 線（平面投影）は `vs.MoveTo` → `vs.LineTo` → `vs.LNewObj`。3D ソリッドは `vs.CreateExtrudeAlongPath`（本体は失敗時 `vs.Poly3D` フォールバック）。
- 本体丸鋼・平面線は **PIO 本体の描画クラス**（`execute_document` が `vs.GetClass(pio)` で取得）、断面記号ソリッドは **`SymbolClass`（無指定なら PIO クラス）** に `vs.SetClass` で割り当て、描画属性を属性ごとの by-class 設定関数ですべてクラス属性に従わせる。

### 表示記号（rebar/symbol.py）

- 配筋標準図（KSE 2008）「鉄筋の表示記号」に従い、呼び径ごとに断面の表示記号を線画のプロファイル（line / circle）へ分解する（D10=●, D13=×, D16=⊘, D19=●, D22=○, D25=⊙, D29=⊗, D32=◎, D35=⊕, D38=●⊕, D41=⊗）。
- 記号の大きさは `呼び径 × MarkScale` を外径とした模式表現。3D 本体の断面円（最外径）とは別に扱う。○ 等の輪郭は `filled=false` の円（押し出すと筒面になり切断が輪郭線）、● は `filled=true` の円（押し出すとソリッドで切断が塗り円）で表す。表にない呼び径は最も近い標準呼び径の記号で近似する。

## 開発プロセス: PR 作成と監視

コード修正を実施する際は以下のプロセスに従う:

1. **PR作成の判断基準**: コード編集後、ユーザーに確認すべき疑義が特にない場合は自動的に PR を作成する。迷いや未確定事項がある場合は PR 作成を保留し先にユーザーに確認する。
2. **PR 作成後の対応**: `subscribe_pr_activity` で CI 結果とレビューコメントを監視する。CI 失敗は原因を診断して修正コミットを push する。CI が全て green でレビュー上の問題もなければ自動的にマージする。
3. **コミットメッセージ**: Claude セッション URL を追加する形式: `https://claude.ai/code/session_<SESSION_ID>`
