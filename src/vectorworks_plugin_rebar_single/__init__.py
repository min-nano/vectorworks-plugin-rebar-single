"""3D パスに沿って 1 本の鉄筋を配置する VectorWorks プラグインオブジェクト。

3D パス(鉄筋の芯線)に鉄筋径(呼び径)を保持し、3D では断面円のパス
押し出しソリッド、平面ビューでは上から見たパスの投影図、断面ビューポート
用には呼び径に応じた表示記号(●/× 等、配筋標準図 KSE 2008)を出力する。

姉妹プロジェクト「配筋」(vectorworks-plugin-rebar)がこの「鉄筋」PIO を
3D パスで多数配置することで、複雑な形状でも断面ビューポートが各鉄筋を
ネイティブに切断でき、正しい位置に断面記号が出る。

処理は 2 フェーズに完全分離されている:

1. 配筋計算フェーズ (``rebar`` パッケージ, vs 非依存)
   PIO のパラメータとパス頂点から、JSON 直列化可能な命令セットを
   組み立てる。
2. 描画フェーズ (``vw`` パッケージ, vs 依存)
   命令セットに従って vs モジュールで実際の描画を行う。

命令セットのスキーマは ``document.py`` を参照。
"""
from __future__ import annotations

import json

from .document import validate_document
from .rebar import SpecError, build_document

__all__ = ['build_document', 'run', 'validate_document']


def run() -> None:
    """PIO のリセットスクリプト本体。

    リセットは頻繁に実行される(移動・編集のたび)ため、エラーは
    モーダルダイアログではなくステータスバー(``vs.Message``)に表示する。
    """
    # vs に依存するモジュールは VectorWorks 上での実行時のみ読み込む。
    # これにより rebar パッケージ(配筋計算フェーズ)は通常の Python 環境でも
    # 利用できる。
    import vs

    from .vw import execute_document
    from .vw.pio import read_pio_input

    try:
        context = read_pio_input()
        if context is None:
            return
        pio_handle, params = context

        # フェーズ1: 配筋計算 → JSON 命令セット。JSON 文字列を経由して
        # 受け渡すことで、命令セットが常に直列化可能(= vs のハンドル等を
        # 含まない)ことを保証する
        document = json.loads(json.dumps(build_document(params)))

        # フェーズ2: 命令セットに従って描画
        execute_document(document, pio_handle)
    except SpecError as error:
        vs.Message(f'鉄筋: {error}')
    except Exception as error:
        vs.Message(f'鉄筋: エラーが発生しました: {error}')
