"""断面の表示記号(●/× 等)を押し出しソリッドの断面プロファイルへ分解する。
vs に依存しない。

配筋標準図(KSE 2008)「鉄筋の表示記号」に従い、呼び径ごとに断面の表示
記号を **塗り形状のプロファイル**(円=disk、中空リング=ring、多角形=polygon)
へ分解する。プロファイルはパスに沿って押し出され、断面ビューポートで
ネイティブに切断されて記号として現れる:

    呼び径  記号
    D10     ●   小さい塗り丸
    D13     ×   斜め十字(帯 2 本)
    D16     ⊘   リング + 斜線(帯 1 本)
    D19     ●   大きい塗り丸(呼び径で自然に大きくなる)
    D22     ○   リング
    D25     ⊙   リング + 中心の塗り丸
    D29     ⊗   リング + 内側の ×(帯 2 本)
    D32     ◎   二重リング
    D35     ⊕   リング + 十字(帯 2 本)
    D38     ●⊕ 塗り丸 + 十字(帯 2 本)
    D41     ⊗   リング + 内側の ×

記号の大きさは ``呼び径 × MarkScale``(= ``size``)を外径とし、断面
(パスに直交する紙面)の原点(0, 0)を基準に組み立てる。押し出しがパスに
沿って配置するため、記号の紙面上の位置合わせは不要(3D ソリッドの実断面が
位置を決める)。○ 等の中空記号はリング(中空)で表す(実断面が塗り環に
なり、壁を薄くして輪郭に見せる)。表にない呼び径は最も近い標準呼び径の
記号で近似する。
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List

from ..document import KIND_DISK, KIND_POLYGON, KIND_RING, Profile

# リングの内径比(壁の薄さ)。1 に近いほど細い輪郭に見える。
_RING_INNER_RATIO = 0.78
# 帯(線)の幅の半径比。
_STRIP_WIDTH_RATIO = 0.16
# 中心点(⊙)の塗り丸の半径比。
_CENTER_DOT_RATIO = 0.24
# 二重リング(◎)の内側リングの外径比。
_INNER_RING_RATIO = 0.5
# 十字(⊕)の帯が円周をわずかに越えて伸びる比率。
_PLUS_EXTEND_RATIO = 1.18


def _disk(radius: float) -> Profile:
    return {'kind': KIND_DISK, 'center': [0.0, 0.0], 'radius': radius}


def _ring(outer: float, inner: float) -> Profile:
    return {'kind': KIND_RING, 'center': [0.0, 0.0], 'outer': outer, 'inner': inner}


def _strip(angle_deg: float, length: float, width: float) -> Profile:
    """原点中心・指定角度の帯(長方形)を塗り多角形プロファイルにする。"""
    theta = math.radians(angle_deg)
    ax, ay = math.cos(theta), math.sin(theta)      # 帯の長さ方向
    px, py = -math.sin(theta), math.cos(theta)     # 幅方向(直交)
    hl, hw = length / 2.0, width / 2.0
    corners = [
        (ax * hl + px * hw, ay * hl + py * hw),
        (ax * hl - px * hw, ay * hl - py * hw),
        (-ax * hl - px * hw, -ay * hl - py * hw),
        (-ax * hl + px * hw, -ay * hl + py * hw),
    ]
    return {'kind': KIND_POLYGON, 'points': [[x, y] for x, y in corners]}


def _cross(r: float, reach: float) -> List[Profile]:
    """斜め十字(× 帯 2 本)。reach は帯の半長(円周まで/箱の対角まで)。"""
    w = r * _STRIP_WIDTH_RATIO
    return [_strip(45.0, 2.0 * reach, w), _strip(-45.0, 2.0 * reach, w)]


def _plus(r: float) -> List[Profile]:
    """十字(縦横の帯 2 本)。円周をわずかに越えて伸びる。"""
    w = r * _STRIP_WIDTH_RATIO
    length = 2.0 * r * _PLUS_EXTEND_RATIO
    return [_strip(0.0, length, w), _strip(90.0, length, w)]


def _dot_sym(r: float) -> List[Profile]:
    """● 塗り丸。"""
    return [_disk(r)]


def _open_circle(r: float) -> List[Profile]:
    """○ リング。"""
    return [_ring(r, r * _RING_INNER_RATIO)]


def _cross_sym(r: float) -> List[Profile]:
    """× 斜め十字(記号の外形いっぱい=箱の対角まで)。"""
    return _cross(r, r * math.sqrt(2.0))


def _circle_slash(r: float) -> List[Profile]:
    """⊘ リング + 斜線 1 本。"""
    w = r * _STRIP_WIDTH_RATIO
    return [_ring(r, r * _RING_INNER_RATIO), _strip(45.0, 2.0 * r, w)]


def _circle_dot(r: float) -> List[Profile]:
    """⊙ リング + 中心の塗り丸。"""
    return [_ring(r, r * _RING_INNER_RATIO), _disk(r * _CENTER_DOT_RATIO)]


def _circle_cross(r: float) -> List[Profile]:
    """⊗ リング + 内側の ×(円周まで)。"""
    return [_ring(r, r * _RING_INNER_RATIO), *_cross(r, r)]


def _double_circle(r: float) -> List[Profile]:
    """◎ 二重リング。"""
    inner_outer = r * _INNER_RING_RATIO
    return [
        _ring(r, r * _RING_INNER_RATIO),
        _ring(inner_outer, inner_outer * _RING_INNER_RATIO),
    ]


def _circle_plus(r: float) -> List[Profile]:
    """⊕ リング + 十字。"""
    return [_ring(r, r * _RING_INNER_RATIO), *_plus(r)]


def _dot_plus(r: float) -> List[Profile]:
    """●⊕ 塗り丸 + 十字。"""
    return [_disk(r * 0.55), *_plus(r)]


# 呼び径 -> 記号の組み立て関数(引数は記号の半径 r = size/2)。
_SYMBOL_BUILDERS: Dict[int, Callable[[float], List[Profile]]] = {
    10: _dot_sym,
    13: _cross_sym,
    16: _circle_slash,
    19: _dot_sym,
    22: _open_circle,
    25: _circle_dot,
    29: _circle_cross,
    32: _double_circle,
    35: _circle_plus,
    38: _dot_plus,
    41: _circle_cross,
}


def _builder_for(nominal: int) -> Callable[[float], List[Profile]]:
    """呼び径に対応する記号組み立て関数を返す(表外は最も近い標準径)。"""
    if nominal in _SYMBOL_BUILDERS:
        return _SYMBOL_BUILDERS[nominal]
    nearest = min(_SYMBOL_BUILDERS, key=lambda d: (abs(d - nominal), d))
    return _SYMBOL_BUILDERS[nearest]


def build_symbol_profiles(nominal: int, size: float) -> List[Profile]:
    """呼び径 ``nominal`` の断面表示記号を外径 ``size`` のプロファイルにする。

    プロファイルは断面(パスに直交する紙面)の原点(0, 0)を基準にした
    塗り形状(disk / ring / polygon)のリスト。``size`` は記号の外径
    (``呼び径 × MarkScale``)で、半径 ``r = size/2``。
    """
    return _builder_for(nominal)(size / 2.0)
