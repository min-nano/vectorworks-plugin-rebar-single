"""JSON 命令セット(ドキュメント)のスキーマ定義と検証。

命令セットは配筋計算フェーズ(``rebar`` パッケージ)が生成し、
描画フェーズ(``vw`` パッケージ)が消費する JSON 直列化可能な dict。
このモジュールは vs に依存しない。

この PIO(鉄筋)は 3D パスに沿って **1 本の鉄筋** を配置するツールで、
出力は 3 系統:

1. 本体(``tube_diameter`` + ``path``): 鉄筋径(最外径)の円形断面をパスに
   沿って押し出した丸鋼のソリッド。3D ビューの鉄筋本体。
2. 平面線(``plan_lines``): 上から見たパスの投影図(2D 線)。
3. 断面記号ソリッド(``symbol_profiles`` + ``path``): 呼び径に応じた表示
   記号(●/× 等、配筋標準図 KSE 2008)の**断面形状**をパスに沿って押し出した
   ソリッド。断面ビューポートはこの 3D ソリッドをネイティブに切断するため、
   どの位置・向きで切っても正しい位置に記号が出る(斜め配筋も可)。記号
   ソリッドは本体とは別のクラス(``SymbolClass`` パラメータ、描画フェーズが
   適用)に割り当て、ビューポートごとにクラス表示を切り替えて 3D では本体、
   断面では記号を見せる運用にする。

本体・平面線は描画フェーズが PIO 本体の描画クラス(``vs.GetClass(pio)``)に
割り当てる。記号ソリッドだけは別クラス(``SymbolClass``)に割り当てる。
作図クラスは命令セットには含めない(クラス管理は描画フェーズ=PIO を扱う側)。

断面プロファイル(``symbol_profiles``)は断面(パスに直交する紙面)上の
塗り形状で、原点(0, 0)中心に組み立てる。押し出しがパスに沿って配置する
ため、記号の紙面上の位置合わせは不要(3D ソリッドの実断面が位置を決める)。
プロファイルの種類:

    {"kind": "disk",    "center": [u, v], "radius": r}          # 塗り円
    {"kind": "ring",    "center": [u, v], "outer": ro, "inner": ri}  # 中空リング
    {"kind": "polygon", "points": [[u, v], ...]}                # 塗り多角形(× の帯等)

スキーマ (version 2):

    {
        "version": 2,
        "path": [[x, y, z], ...],   # 3D パス頂点(鉄筋の芯線, PIO ローカル座標 mm)
        "tube_diameter": 14.0,      # 本体丸鋼の直径(最外径, mm)
        "plan_lines": [ {"start": [x, y], "end": [x, y]} ],
        "symbol_profiles": [ <profile>, ... ]
    }

スキーマを変更するときは ``DOCUMENT_VERSION`` の互換性に注意し、
TypedDict 定義・docstring・``validate_document()`` とテストも併せて
更新すること。
"""
from __future__ import annotations

from typing import Any, Dict, List, TypedDict

DOCUMENT_VERSION = 2

# symbol_profiles の kind。
KIND_DISK = 'disk'
KIND_RING = 'ring'
KIND_POLYGON = 'polygon'
PROFILE_KINDS = (KIND_DISK, KIND_RING, KIND_POLYGON)

# 断面プロファイル(線・円で持つキーが異なる不均質な dict)。実行時検証
# (``validate_document``)で形を保証する ``Dict[str, Any]`` として扱う。
Profile = Dict[str, Any]


class PlanLineCommand(TypedDict):
    start: List[float]
    end: List[float]


class Document(TypedDict):
    version: int
    path: List[List[float]]
    tube_diameter: float
    plan_lines: List[PlanLineCommand]
    symbol_profiles: List[Profile]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_point_2d(value: Any, where: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(_is_number(v) for v in value)
    ):
        raise ValueError(f'{where} は [x, y] の数値ペアである必要があります: {value!r}')


def _validate_point_3d(value: Any, where: str) -> None:
    if (
        not isinstance(value, list)
        or len(value) != 3
        or not all(_is_number(v) for v in value)
    ):
        raise ValueError(f'{where} は [x, y, z] の数値である必要があります: {value!r}')


def _validate_path(value: Any) -> None:
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError('path は 2 点以上の頂点リストである必要があります')
    for i, vertex in enumerate(value):
        _validate_point_3d(vertex, f'path[{i}]')


def _validate_plan_line(command: Any, index: int) -> None:
    where = f'plan_lines[{index}]'
    if not isinstance(command, dict):
        raise ValueError(f'{where} は dict である必要があります')
    _validate_point_2d(command.get('start'), f'{where}.start')
    _validate_point_2d(command.get('end'), f'{where}.end')


def _validate_positive(value: Any, where: str) -> None:
    if not _is_number(value):
        raise ValueError(f'{where} は数値である必要があります: {value!r}')
    if value <= 0:
        raise ValueError(f'{where} は正の値である必要があります: {value!r}')


def _validate_profile(profile: Any, index: int) -> None:
    where = f'symbol_profiles[{index}]'
    if not isinstance(profile, dict):
        raise ValueError(f'{where} は dict である必要があります')
    kind = profile.get('kind')
    if kind == KIND_DISK:
        _validate_point_2d(profile.get('center'), f'{where}.center')
        _validate_positive(profile.get('radius'), f'{where}.radius')
    elif kind == KIND_RING:
        _validate_point_2d(profile.get('center'), f'{where}.center')
        _validate_positive(profile.get('outer'), f'{where}.outer')
        _validate_positive(profile.get('inner'), f'{where}.inner')
        if profile['inner'] >= profile['outer']:
            raise ValueError(f'{where}.inner は outer より小さい必要があります')
    elif kind == KIND_POLYGON:
        points = profile.get('points')
        if not isinstance(points, list) or len(points) < 3:
            raise ValueError(f'{where}.points は 3 点以上の頂点リストである必要があります')
        for i, point in enumerate(points):
            _validate_point_2d(point, f'{where}.points[{i}]')
    else:
        raise ValueError(
            f'{where}.kind は {PROFILE_KINDS} のいずれかである必要があります: {kind!r}'
        )


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
    _validate_path(document.get('path'))
    _validate_positive(document.get('tube_diameter'), 'tube_diameter')

    plan_lines = document.get('plan_lines')
    if not isinstance(plan_lines, list):
        raise ValueError('plan_lines はリストである必要があります')
    for index, command in enumerate(plan_lines):
        _validate_plan_line(command, index)

    profiles = document.get('symbol_profiles')
    if not isinstance(profiles, list):
        raise ValueError('symbol_profiles はリストである必要があります')
    for index, profile in enumerate(profiles):
        _validate_profile(profile, index)
    return document  # type: ignore[return-value]
