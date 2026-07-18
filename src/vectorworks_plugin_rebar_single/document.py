"""JSON 命令セット(ドキュメント)のスキーマ定義と検証。

命令セットは配筋計算フェーズ(``rebar`` パッケージ)が生成し、
描画フェーズ(``vw`` パッケージ)が消費する JSON 直列化可能な dict。
このモジュールは vs に依存しない。

この PIO(鉄筋)は 3D パスに沿って **1 本の鉄筋** を配置するシンプルな
ツールで、出力は 3 系統:

1. 3D ソリッド(``solid``): 鉄筋径の円形断面をパスに沿って押し出した
   ソリッド。断面ビューポートはこの 3D ソリッドをネイティブに切断できる
   ため、複雑な形状でも正しい位置に断面が出る。
2. 平面線(``plan_lines``): 上から見たパスの投影図(2D 線)。デザイン
   レイヤの平面ビュー(Top/Plan)に表示する。
3. 断面 2D コンポーネント(``cut_marks``): 断面ビューポートの
   「2D コンポーネントを表示」で表示される記号。鉄筋径に応じた ●/× 等
   (配筋標準図 KSE 2008 の表示記号)。前後/左右どちらの断面でも同じ記号
   を出すため、両方の target 分を生成する。

図形の作図クラスは命令セットには含まれない。すべての図形は描画フェーズが
PIO 本体の描画クラス(``vs.GetClass(pio)``)に割り当てる(クラス指定は
PIO を扱う側=PIO 本体へのクラス割り当てで管理する)。

スキーマ (version 1):

    {
        "version": 1,
        "solid": {
            # 3D ソリッド(円形断面のパス押し出し)。描画フェーズが
            # ``CreateExtrudeAlongPath`` で生成する(失敗時は 3D ポリラインへ
            # フォールバック)。座標は PIO のローカル座標 (mm)。
            "diameter": 14.0,               # 断面円の直径 = 最外径 (mm)
            "path": [[x, y, z], ...]        # 3D パス頂点(鉄筋の芯線)
        },
        "plan_lines": [
            {
                # 上から見たパスの投影図(2D 線)。座標は PIO のローカル
                # 座標 (mm)。デザインレイヤの平面ビューに表示する。
                "start": [x1, y1],
                "end": [x2, y2]
            }
        ],
        "cut_marks": [
            {
                # 断面 2D コンポーネントに描く記号。target はどの 2D
                # コンポーネントに置くか:
                #   "front_back" = 前後の断面 (2D component 定数 6,
                #                  紙面 u=ローカル X, v=ローカル Z)
                #   "left_right" = 左右の断面 (2D component 定数 9,
                #                  紙面 u=ローカル Y, v=ローカル Z)
                # 鉄筋を端から見た記号は向きに依存しないため、両方の
                # target に同じ形の記号を生成する。ただし記号は原点固定では
                # なく、鉄筋の断面位置(パスの重心を各断面の紙面へ投影した点、
                # front_back は (X, Z)・left_right は (Y, Z))へ平行移動して
                # 置く。断面ビューポートは 3D の鉄筋を実位置で切断するため、
                # 記号も同じ位置に出さないと本体と食い違う(原点固定だと PIO の
                # ローカル原点とパスの実位置の差だけ記号がずれる)。primitives は
                # 記号を構成する線・円のプリミティブ(紙面ローカル座標 mm):
                #   {"kind": "line",   "start": [u, v], "end": [u, v]}
                #   {"kind": "circle", "center": [u, v], "radius": r,
                #    "filled": true|false}
                "target": "front_back",
                "primitives": [ ... ]
            }
        ]
    }

スキーマを変更するときは ``DOCUMENT_VERSION`` の互換性に注意し、
TypedDict 定義・docstring・``validate_document()`` とテストも併せて
更新すること。
"""
from __future__ import annotations

from typing import Any, Dict, List, TypedDict

DOCUMENT_VERSION = 1

# cut_marks の target に指定できる値。
TARGET_FRONT_BACK = 'front_back'
TARGET_LEFT_RIGHT = 'left_right'
CUT_TARGETS = (TARGET_FRONT_BACK, TARGET_LEFT_RIGHT)

# primitives の kind。
KIND_LINE = 'line'
KIND_CIRCLE = 'circle'
PRIMITIVE_KINDS = (KIND_LINE, KIND_CIRCLE)


# 記号を構成するプリミティブ(線 or 円)。線・円で持つキーが異なる
# 不均質な dict のため、TypedDict の Union ではなく実行時検証
# (``validate_document``)で形を保証する ``Dict[str, Any]`` として扱う。
# 形式:
#   線: {"kind": "line",   "start": [u, v], "end": [u, v]}
#   円: {"kind": "circle", "center": [u, v], "radius": r, "filled": bool}
Primitive = Dict[str, Any]


class Solid(TypedDict):
    diameter: float
    path: List[List[float]]


class PlanLineCommand(TypedDict):
    start: List[float]
    end: List[float]


class CutMarkCommand(TypedDict):
    target: str
    primitives: List[Primitive]


class Document(TypedDict):
    version: int
    solid: Solid
    plan_lines: List[PlanLineCommand]
    cut_marks: List[CutMarkCommand]


def _validate_point_2d(value: Any, where: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(isinstance(v, (int, float)) for v in value)
    ):
        raise ValueError(f'{where} は [x, y] の数値ペアである必要があります: {value!r}')


def _validate_point_3d(value: Any, where: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 3
        or not all(isinstance(v, (int, float)) for v in value)
    ):
        raise ValueError(f'{where} は [x, y, z] の数値である必要があります: {value!r}')


def _validate_solid(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError('solid は dict である必要があります')
    diameter = value.get('diameter')
    if not isinstance(diameter, (int, float)) or isinstance(diameter, bool):
        raise ValueError(f'solid.diameter は数値である必要があります: {diameter!r}')
    if diameter <= 0:
        raise ValueError(f'solid.diameter は正の値である必要があります: {diameter!r}')
    path = value.get('path')
    if not isinstance(path, list) or len(path) < 2:
        raise ValueError('solid.path は 2 点以上の頂点リストである必要があります')
    for i, vertex in enumerate(path):
        _validate_point_3d(vertex, f'solid.path[{i}]')


def _validate_plan_line(command: Any, index: int) -> None:
    where = f'plan_lines[{index}]'
    if not isinstance(command, dict):
        raise ValueError(f'{where} は dict である必要があります')
    _validate_point_2d(command.get('start'), f'{where}.start')
    _validate_point_2d(command.get('end'), f'{where}.end')


def _validate_primitive(primitive: Any, where: str) -> None:
    if not isinstance(primitive, dict):
        raise ValueError(f'{where} は dict である必要があります')
    kind = primitive.get('kind')
    if kind == KIND_LINE:
        _validate_point_2d(primitive.get('start'), f'{where}.start')
        _validate_point_2d(primitive.get('end'), f'{where}.end')
    elif kind == KIND_CIRCLE:
        _validate_point_2d(primitive.get('center'), f'{where}.center')
        radius = primitive.get('radius')
        if not isinstance(radius, (int, float)) or isinstance(radius, bool):
            raise ValueError(f'{where}.radius は数値である必要があります: {radius!r}')
        if radius <= 0:
            raise ValueError(f'{where}.radius は正の値である必要があります: {radius!r}')
        if not isinstance(primitive.get('filled'), bool):
            raise ValueError(f'{where}.filled は bool である必要があります')
    else:
        raise ValueError(
            f'{where}.kind は {PRIMITIVE_KINDS} のいずれかである必要があります: {kind!r}'
        )


def _validate_cut_mark(command: Any, index: int) -> None:
    where = f'cut_marks[{index}]'
    if not isinstance(command, dict):
        raise ValueError(f'{where} は dict である必要があります')
    if command.get('target') not in CUT_TARGETS:
        raise ValueError(
            f'{where}.target は {CUT_TARGETS} のいずれかである必要があります: '
            f'{command.get("target")!r}'
        )
    primitives = command.get('primitives')
    if not isinstance(primitives, list) or not primitives:
        raise ValueError(f'{where}.primitives は 1 個以上のリストである必要があります')
    for i, primitive in enumerate(primitives):
        _validate_primitive(primitive, f'{where}.primitives[{i}]')


def validate_document(document: Any) -> Document:
    """命令セットを検証し、型付きの ``Document`` として返す。

    JSON 由来の信頼できない入力を受けるため引数は ``Any`` とし、
    検証に通った値だけを ``Document`` 型として扱う。
    不正な場合は ``ValueError`` を送出する。
    """
    if not isinstance(document, dict):
        raise ValueError('命令セットは dict である必要があります')
    if document.get('version') != DOCUMENT_VERSION:
        raise ValueError(
            f'命令セットの version が {DOCUMENT_VERSION} ではありません: '
            f'{document.get("version")!r}'
        )
    _validate_solid(document.get('solid'))
    for key, validator in (
        ('plan_lines', _validate_plan_line),
        ('cut_marks', _validate_cut_mark),
    ):
        commands = document.get(key)
        if not isinstance(commands, list):
            raise ValueError(f'{key} はリストである必要があります')
        for index, command in enumerate(commands):
            validator(command, index)
    return document  # type: ignore[return-value]
