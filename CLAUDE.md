# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## このリポジトリについて

3D パスに沿って **1 本の鉄筋** を配置するシンプルな VectorWorks **プラグインオブジェクト（PIO）** スクリプトです。姉妹プロジェクト `vectorworks-plugin-rebar`（配筋）と同じアーキテクチャ・コーディング規約・実行時自動更新の仕組みを踏襲しています。

PIO は 3D パス図形 `鉄筋` として VectorWorks に登録され（README の登録手順参照）、3D パス＝鉄筋の芯線、呼び径（`D13` 等）を保持する。出力は 3 系統:

1. **3D**: 鉄筋径（最外径）の円形断面をパスに沿って押し出したソリッド（`vs.CreateExtrudeAlongPath`）。断面ビューポートはこの 3D ソリッドをネイティブに切断できるため、折れ・フックのある複雑な形状でも正しい位置に断面が出る。生成に失敗する環境（VW バージョン差など）では 3D ポリライン（芯線）へフォールバックする。
2. **平面（Top/Plan）**: 上から見たパスの投影図（2D 線）。デザインレイヤの平面ビューは regen をそのまま表示する。
3. **断面 2D コンポーネント**: 断面ビューポートの「2D コンポーネントを表示」で表示される表示記号。呼び径に応じた ●／× 等（配筋標準図 KSE 2008「鉄筋の表示記号」）。鉄筋を端から見た記号は向きに依存しないため、前後の断面（6）・左右の断面（9）の両方に同じ記号を設定する。

すべての図形は **PIO 本体の描画クラス**（`vs.GetClass(pio)`）に割り当てる。クラス指定は PIO を扱う側（PIO 本体へのクラス割り当て）で管理するため、本パッケージは固有のクラス名を持たない（塗り記号「●」だけはクラス塗りに関わらず実塗りにする）。

## 配筋（vectorworks-plugin-rebar）との関係

姉妹プロジェクト「配筋」PIO が、この「鉄筋」PIO を 3D パスで多数配置して配筋全体を組み立てる 2 段階構成の下位オブジェクト。1 本ごとを独立した鉄筋オブジェクト（実体のある 3D ソリッド）にすることで、断面ビューポートが各鉄筋を個別に切断でき、単一の配筋オブジェクトが多方向の鉄筋を 1 つの 2D コンポーネントで表現していたときの「切断位置に関係なく全コンポーネントが表示される」問題を回避する。**まず本 PIO を VectorWorks 上で検証してから配筋側の改修を行う**方針。

## アーキテクチャ: 2 フェーズ分離

処理は **配筋計算フェーズ** と **VectorWorks 描画フェーズ** に完全分離されている。両フェーズは JSON 直列化可能な**命令セット（ドキュメント）**だけで接続され、`vs` との密結合を避けることで検証や VectorWorks バージョンアップ対応を容易にしている。

1. **配筋計算フェーズ（`rebar` サブパッケージ）** — `vs` に一切依存しない。PIO のパラメータとパス頂点（プレーンな dict）から、描くべき図形を命令セット（dict）として組み立てる。通常の Python 環境で単体実行・検証できる。
2. **描画フェーズ（`vw` サブパッケージ）** — `vs` だけに依存し、鉄筋の知識（呼び径・記号の意味等）を持たない。命令セットを検証（`validate_document`）してから vs API で描画する。

命令セットのスキーマ（version・solid/plan_lines/cut_marks の各形式）は `document.py` の docstring に定義されている。スキーマを変更するときは `DOCUMENT_VERSION` の互換性に注意し、`TypedDict` 定義・docstring・`validate_document()` とテストも併せて更新すること。`run()` は両フェーズの間で `json.dumps`/`json.loads` を通すため、命令セットに直列化不能なオブジェクト（vs ハンドル等）を入れてはならない。

## パッケージ構造

```
src/
    vectorworks_plugin_rebar_single/  # pip インストール可能なパッケージ本体
        __init__.py       # run() を公開 (PIO 読取 → 計算 → JSON 命令セット → 描画)
        document.py       # 命令セットのスキーマ定義・検証 (vs 非依存)
        rebar/            # フェーズ1: 計算 (vs 非依存)
            __init__.py   # build_document(params) -> dict / 既定値定数
            spec.py       # 呼び径パース (D13 / NFKC 正規化) と最外径表
            symbol.py     # 標準図の表示記号 → 線・円プリミティブ
        vw/               # フェーズ2: VectorWorks 描画 (vs 依存)
            __init__.py   # execute_document(document, pio_handle) -> 実行数 dict
            pio.py        # PIO コンテキスト読取 (パラメータ・パス頂点 → params dict)
            draw.py       # 2D 線・円・3D ソリッド押し出し (by-class 属性)
            component.py  # 断面 2D コンポーネントの設定 (Set2DComponentGroup)
main.py                  # VectorWorks に登録する PIO スクリプト (実行時に自動インストール・更新)
tests/                   # pytest 用テスト (CI は vs.py スタブを GitHub からダウンロード)
pyproject.toml           # パッケージメタデータ
```

`vs` を import してよいのは `vw` サブパッケージ内・`run()` 関数内・`main.py` の設定フォルダ検出（いずれも関数内の遅延 import）だけ。`rebar` サブパッケージや `document.py` に `vs` への依存を持ち込まないこと。テストもこの分離に従う: `tests/test_rebar_*.py`・`tests/test_document.py` は vs モック不要、`tests/test_vw_*.py`・`tests/test_init.py` は手書きの命令・パラメータを vs モックで実行して検証する。

## コーディング規約: 型注釈

すべての関数・メソッド（テストコード・モック用クロージャ含む）に引数と戻り値の型注釈を付ける。型検査は mypy で行い、CI で `mypy` を実行する（設定は `pyproject.toml` の `[tool.mypy]`、`disallow_untyped_defs` 有効）。

- 各モジュール先頭に `from __future__ import annotations` を置く。Python 3.9 互換を保ちつつ `list[str]` / `X | None` 構文を使うため。
- 命令セットの型は `document.py` の `TypedDict`（`Document` / `Solid` / `PlanLineCommand` / `CutMarkCommand`）を使う。記号のプリミティブ（線・円で持つキーが異なる不均質な dict）は `Primitive = Dict[str, Any]` とし、実行時検証（`validate_document`）で形を保証する。
- `vs` モジュールは型スタブが存在しないため `ignore_missing_imports` で許容し、vs ハンドルは `Any` で扱う。VectorWorks 公式 `vs.py` スタブ（`tests/vs.py`）は型検査対象から除外している。
- 検証前の命令セット（JSON 由来の信頼できない入力）を受ける関数（`validate_document()` / `execute_document()`）の引数は `Any` とし、検証済みの値だけを `Document` 型として扱う。

## スクリプトの実行方法

このスクリプトは単独の Python プログラムとして動作しません。**VectorWorks 内で PIO のリセットスクリプトとして実行する必要があります**。`vs` モジュールは VectorWorks 独自の Python スクリプト API であり、pip でインストールすることはできません。

テストは VectorWorks の公式 `vs.py` スタブをモック対象として `pytest` で実行します（`.github/workflows/test.yml` 参照）。

## 実行時自動更新（main.py）

配筋（rebar）の main.py と同じ仕組み（GitHub `main` ブランチのコミット SHA 比較 → アーカイブ直接展開 → 依存は pip）。パッケージ名・リポジトリ名だけが異なる。**開発初期は頻繁に変更して試すため、リセットのたびに毎回更新を確認する**。更新した場合はキャッシュ済みモジュールを破棄するため、VectorWorks を再起動しなくても次のリセットから新しいコードが使われる。

## PIO スクリプトの処理フロー

`vectorworks_plugin_rebar_single.run()` は PIO のリセットのたびに以下を行う:

1. **PIO コンテキスト読取（`vw/pio.py`）** — `vs.GetCustomObjectInfo()` で PIO ハンドルを取得し、`vs.GetRField` でパラメータ（`Bar` / `MarkScale`）を、`vs.GetCustomObjectPath` + `vs.GetPolyPt3D`（**0 始まり**インデックス）でパス頂点を読む。数値フィールドは単位付き文字列を許容し、解釈できないフィールドはキーを省いて既定値に委ねる。
2. **計算（フェーズ1）** — `rebar.build_document(params)` で JSON 命令セットを組み立てる。呼び径の形式不正・パス不足は `SpecError`（ユーザー向け日本語メッセージ）。
3. **JSON 経由の受け渡し** — `json.dumps` → `json.loads` を通し直列化可能性を保証。
4. **描画（フェーズ2）** — `vw.execute_document(document, pio_handle)` が検証後、3D ソリッド → 平面線（regen）→ 断面 2D コンポーネントの順で描画する。
5. **エラー表示** — リセットは頻繁に実行されるためモーダルダイアログは使わず、`vs.Message` でステータスバーに表示する（`SpecError` は入力の直し方が分かるメッセージ）。

### 3D ソリッド（vw/draw.py）

- **`vs.CreateExtrudeAlongPath(pathHandle, profileHandle)`** で断面円をパスに沿って押し出したソリッドを作る。パスは NURBS 曲線（`vs.CreateNurbsCurve` + `vs.AddVertex3D`、次数 1＝折れを丸めない線形補間）、プロファイルは原点中心の円（`vs.Oval`）。
- 生成に失敗する環境（関数が無い VW バージョン・NULL 戻り・例外）では **3D ポリライン（芯線）へフォールバック**し、3D ビューに鉄筋が出るようにする。
- **プロファイルの向き・原点、押し出しの生成可否、生成後の元パス/プロファイルの後始末は VectorWorks 上で最終確認する**（描画フェーズは VW 上で検証する方針）。

### 断面 2D コンポーネント（vw/component.py）

- **`vs.Set2DComponentGroup(pio, group, component)`（VW 2019+）** で PIO の 2D コンポーネントグループを設定する。component 定数は公式リファレンス（Table - 2D components）に基づく: `0`=未設定, `1`=Top, `2`=Bottom, `3`=Top/Bottom Cut, `4`=Front, `5`=Back, **`6`=Front and Back Cut**, `7`=Left, `8`=Right, **`9`=Left and Right Cut**, `10`=Top/Plan。
- 命令セットの `target` との対応: `front_back` → 6（紙面 u=ローカル X・v=ローカル Z）、`left_right` → 9（紙面 u=ローカル Y・v=ローカル Z）。鉄筋を端から見た記号は向きに依存しないため両方に同じ記号を設定する。
- **平面線は通常の 2D 図形（regen）として描く**。**断面記号は `Set2DComponentGroup` で 6/9 に割り当てた後、元グループを `vs.DelObject` で regen から削除する**（コンポーネント側へジオメトリをコピーするため、regen の元グループを消しても断面ビューポートには記号が残る）。命令が無い target は NULL ハンドルを設定して前回リセットのコンポーネントを消す。
- **2D 線・円は画面平面（screen plane, planar ref 0）に置く**（`vw/draw.py` の `set_screen_plane`）。`Set2DComponentGroup` は画面平面のオブジェクトのグループを要求するため。
- **`vs.SetTopPlan2DComp(pio, 0)` で Top/Plan ビューを Top（非断面）に固定する**。
- **断面記号の紙面上の配置位置（原点に置くか切断位置を追うか）・左右ビューの鏡像の扱いは VectorWorks 上で最終確認する**。3D ソリッドが実体としてあるため、断面ビューポートは各鉄筋を実切断位置で切れる前提で設計しているが、2D コンポーネントの表示位置は VW の挙動に依存する。

### 描画の規約（vw/draw.py）

- 2D 線は `vs.MoveTo` → `vs.LineTo` → `vs.LNewObj`、2D 円は `vs.Oval` → `vs.LNewObj`（塗り記号は `vs.SetFPat(handle, 1)` で実塗り）、3D は `vs.CreateExtrudeAlongPath`（失敗時 `vs.Poly3D` フォールバック）。
- すべての図形を **PIO 本体の描画クラス**（`execute_document` が `vs.GetClass(pio)` で 1 回取得）に `vs.SetClass` で割り当て、描画属性を属性ごとの by-class 設定関数ですべてクラス属性に従わせる（塗り記号の実塗りだけ例外）。

### 表示記号（rebar/symbol.py）

- 配筋標準図（KSE 2008）「鉄筋の表示記号」に従い、呼び径ごとに断面の表示記号を線・円のプリミティブへ分解する（D10=●, D13=×, D16=⊘, D19=●, D22=○, D25=⊙, D29=⊗, D32=◎, D35=⊕, D38=●⊕, D41=⊗）。
- 記号の大きさは `呼び径 × MarkScale` を外径とした模式表現。3D ソリッドの断面円（最外径）とは別に扱う。表にない呼び径は最も近い標準呼び径の記号で近似する。

## 開発プロセス: PR 作成と監視

コード修正を実施する際は以下のプロセスに従う:

1. **PR作成の判断基準**: コード編集後、ユーザーに確認すべき疑義が特にない場合は自動的に PR を作成する。迷いや未確定事項がある場合は PR 作成を保留し先にユーザーに確認する。
2. **PR 作成後の対応**: `subscribe_pr_activity` で CI 結果とレビューコメントを監視する。CI 失敗は原因を診断して修正コミットを push する。CI が全て green でレビュー上の問題もなければ自動的にマージする。
3. **コミットメッセージ**: Claude セッション URL を追加する形式: `https://claude.ai/code/session_<SESSION_ID>`
