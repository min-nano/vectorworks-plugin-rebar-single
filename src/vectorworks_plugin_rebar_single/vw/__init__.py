"""フェーズ2: VectorWorks 描画(1 本の鉄筋)。vs だけに依存する。

命令セットを検証(``validate_document``)してから vs API で描画する。
配筋の知識(呼び径・記号の意味等)は持たず、命令セットの図形をそのまま
描く。

すべての図形は **PIO 本体の描画クラス**(``vs.GetClass(pio)``)に割り当て、
描画属性を by-class にする(クラス指定は PIO を扱う側=PIO 本体への
クラス割り当てで管理する)。

描画順:

1. 3D ソリッド(solid) — 断面円をパスに沿って押し出したソリッド。断面
   ビューポートがネイティブに切断できるため、複雑な形状でも正しい位置に
   断面が出る。生成に失敗する環境では 3D ポリライン(芯線)へフォール
   バックする。
2. 平面線(plan_lines) — 上から見たパスの投影図。通常の 2D 図形(regen)
   として描く。デザインレイヤの平面ビューは regen をそのまま表示する。
3. 断面記号(cut_marks) — target ごとにグループへまとめ、PIO の 2D
   コンポーネント(前後の断面=6・左右の断面=9)に設定した後、元グループを
   ``vs.DelObject`` で regen から削除する。``Set2DComponentGroup`` は
   コンポーネント側へジオメトリをコピーするため、regen の元グループを
   消しても断面ビューポートには記号が残り、平面ビューには漏れない。
   命令が無い target は NULL を設定して前回リセットの残骸を消す。
"""
from __future__ import annotations

from typing import Any, Dict, List

import vs

from ..document import (
    CUT_TARGETS,
    KIND_CIRCLE,
    KIND_LINE,
    CutMarkCommand,
    PlanLineCommand,
    Primitive,
    Solid,
    validate_document,
)
from .component import (
    TARGET_COMPONENTS,
    component_set_succeeded,
    set_component_group,
    set_top_plan_view_component,
)
from .draw import draw_circle_2d, draw_line_2d, draw_solid_sweep

__all__ = ['execute_document']


def _pio_class(pio_handle: Any) -> str:
    """PIO 本体の描画クラス名を返す。取得できない場合は空文字。"""
    try:
        name = vs.GetClass(pio_handle)
    except Exception:
        return ''
    return name if isinstance(name, str) else ''


def _execute_solid(solid: Solid, class_name: str) -> int:
    """3D ソリッド(断面円のパス押し出し)を描く。"""
    draw_solid_sweep(solid['diameter'], solid['path'], class_name)
    return 1


def _execute_plan_lines(
    commands: List[PlanLineCommand], class_name: str
) -> int:
    """plan_lines(投影図)を通常の 2D 図形(regen)として描く。"""
    for command in commands:
        draw_line_2d(command['start'], command['end'], class_name)
    return len(commands)


def _draw_primitive(primitive: Primitive, class_name: str) -> None:
    """断面記号のプリミティブ(線 or 円)を 1 個描く。"""
    if primitive['kind'] == KIND_LINE:
        draw_line_2d(primitive['start'], primitive['end'], class_name)
    elif primitive['kind'] == KIND_CIRCLE:
        draw_circle_2d(
            primitive['center'],
            primitive['radius'],
            primitive['filled'],
            class_name,
        )


def _execute_cut_marks(
    pio_handle: Any, commands: List[CutMarkCommand], class_name: str
) -> int:
    """cut_marks を 2D コンポーネントに割り当て、regen からは取り除く。

    デザインレイヤの平面ビューは regen をそのまま表示するため、割り当て後に
    元グループを ``vs.DelObject`` で regen から削除する。命令が無い target は
    NULL を設定して前回リセットの残骸を消す。
    """
    by_target: Dict[str, List[CutMarkCommand]] = {
        target: [] for target in CUT_TARGETS
    }
    for command in commands:
        by_target[command['target']].append(command)

    count = 0
    for target, component in TARGET_COMPONENTS.items():
        marks = by_target[target]
        if not marks:
            # 前回リセットの断面記号が残らないよう空のコンポーネントは削除する
            set_component_group(pio_handle, None, component)
            continue
        vs.BeginGroup()
        for mark in marks:
            for primitive in mark['primitives']:
                _draw_primitive(primitive, class_name)
        vs.EndGroup()
        group = vs.LNewObj()
        if component_set_succeeded(
            set_component_group(pio_handle, group, component)
        ):
            count += len(marks)
        # 断面記号を regen(平面ビュー)から取り除く。コンポーネント側には
        # コピーが残るため断面ビューポートには記号が表示される。
        vs.DelObject(group)
    return count


def execute_document(document: Any, pio_handle: Any) -> Dict[str, int]:
    """命令セットを検証してから描画し、実行数を返す。"""
    validated = validate_document(document)
    class_name = _pio_class(pio_handle)

    counts = {
        'solid': _execute_solid(validated['solid'], class_name),
        'plan_lines': _execute_plan_lines(validated['plan_lines'], class_name),
        'cut_marks': _execute_cut_marks(
            pio_handle, validated['cut_marks'], class_name
        ),
    }
    # Top/Plan ビューが断面コンポーネントを表示しないよう Top に固定する
    set_top_plan_view_component(pio_handle)
    return counts
