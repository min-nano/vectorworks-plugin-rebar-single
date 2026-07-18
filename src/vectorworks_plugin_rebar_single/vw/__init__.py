"""フェーズ2: VectorWorks 描画(1 本の鉄筋)。vs だけに依存する。

命令セットを検証(``validate_document``)してから vs API で描画する。
配筋の知識(呼び径・記号の意味等)は持たず、命令セットの図形をそのまま
描く。

描画:

1. 本体丸鋼(tube) — 最外径の円形断面をパスに沿って押し出したソリッド。
   PIO 本体の描画クラス(``vs.GetClass(pio)``)に割り当てる。生成に失敗する
   環境では 3D ポリライン(芯線)へフォールバックする。
2. 平面線(plan_lines) — 上から見たパスの投影図。PIO 本体の描画クラス。
3. 断面記号ソリッド(symbol_profiles) — 記号の断面形状をパスに沿って
   押し出したソリッド。**別クラス**(``symbol_class``, ``SymbolClass``
   パラメータ)に割り当てる。断面ビューポートがネイティブに切断して記号
   として現れる。3D ビューでは記号クラスを非表示、断面ビューポートでは本体
   クラスを非表示、とビューポートのクラス表示で切り替える運用。

2D コンポーネントは使わない(ローカル 6 軸・紙面平面の制約と位置ずれの
問題があるため、実体のソリッドをネイティブに切断する方式へ変更した)。
"""
from __future__ import annotations

from typing import Any, Dict, List

import vs

from ..document import (
    KIND_DISK,
    KIND_POLYGON,
    KIND_RING,
    PlanLineCommand,
    Profile,
    validate_document,
)
from .draw import (
    draw_line_2d,
    draw_symbol_disk,
    draw_symbol_polygon,
    draw_symbol_ring,
    draw_tube,
)

__all__ = ['execute_document']


def _pio_class(pio_handle: Any) -> str:
    """PIO 本体の描画クラス名を返す。取得できない場合は空文字。"""
    try:
        name = vs.GetClass(pio_handle)
    except Exception:
        return ''
    return name if isinstance(name, str) else ''


def _execute_plan_lines(
    commands: List[PlanLineCommand], class_name: str
) -> int:
    """plan_lines(投影図)を通常の 2D 図形(regen)として描く。"""
    for command in commands:
        draw_line_2d(command['start'], command['end'], class_name)
    return len(commands)


def _execute_symbol_profile(
    profile: Profile, path: List[List[float]], class_name: str
) -> None:
    """断面記号の 1 プロファイルをパスに沿って押し出す。"""
    kind = profile['kind']
    if kind == KIND_DISK:
        draw_symbol_disk(profile['center'], profile['radius'], path, class_name)
    elif kind == KIND_RING:
        draw_symbol_ring(
            profile['center'],
            profile['outer'],
            profile['inner'],
            path,
            class_name,
        )
    elif kind == KIND_POLYGON:
        draw_symbol_polygon(profile['points'], path, class_name)


def execute_document(
    document: Any, pio_handle: Any, symbol_class: str = ''
) -> Dict[str, int]:
    """命令セットを検証してから描画し、実行数を返す。

    symbol_class は断面記号ソリッドに割り当てるクラス名(``SymbolClass``
    パラメータ)。空の場合は PIO 本体の描画クラスに割り当てる。
    """
    validated = validate_document(document)
    pio_class = _pio_class(pio_handle)
    path = validated['path']

    draw_tube(validated['tube_diameter'], path, pio_class)

    plan_count = _execute_plan_lines(validated['plan_lines'], pio_class)

    symbol_class_name = symbol_class if symbol_class else pio_class
    for profile in validated['symbol_profiles']:
        _execute_symbol_profile(profile, path, symbol_class_name)

    return {
        'tube': 1,
        'plan_lines': plan_count,
        'symbol_profiles': len(validated['symbol_profiles']),
    }
