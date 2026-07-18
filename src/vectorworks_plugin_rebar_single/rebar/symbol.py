"""断面の表示記号(●/× 等)の組み立て。vs に依存しない。

配筋標準図(KSE 2008)「鉄筋の表示記号」に従い、呼び径ごとに断面の
表示記号を線・円のプリミティブへ分解する:

    呼び径  記号
    D10     ●   小さい塗り丸
    D13     ×   斜め十字
    D16     ⊘   丸 + 斜線 1 本
    D19     ●   大きい塗り丸(呼び径で自然に大きくなる)
    D22     ○   丸
    D25     ⊙   丸 + 中心の点
    D29     ⊗   丸 + 内側の × (斜め十字)
    D32     ◎   二重丸
    D35     ⊕   丸 + 十字線(縦横)
    D38     ●⊕ 塗り丸 + 十字線
    D41     ⊗   丸 + 内側の ×

記号の大きさは ``呼び径 × MarkScale``(= ``size``)を外径とし、中心
(0, 0)を基準に組み立てる。標準図の記号は視認性のため実寸より大きい
模式表現で、3D ソリッドの断面円(最外径)とは別に扱う。表にない呼び径は
最も近い標準呼び径の記号で近似する。
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List

from ..document import KIND_CIRCLE, KIND_LINE, Primitive

# 45° 方向の単位長(円周上の斜め点の座標係数)。
_DIAG = math.sqrt(0.5)


def _line(x1: float, y1: float, x2: float, y2: float) -> Primitive:
    return {'kind': KIND_LINE, 'start': [x1, y1], 'end': [x2, y2]}


def _circle(radius: float, filled: bool) -> Primitive:
    return {
        'kind': KIND_CIRCLE,
        'center': [0.0, 0.0],
        'radius': radius,
        'filled': filled,
    }


def _dot(r: float) -> List[Primitive]:
    """● 塗り丸。"""
    return [_circle(r, True)]


def _open_circle(r: float) -> List[Primitive]:
    """○ 丸。"""
    return [_circle(r, False)]


def _cross(r: float) -> List[Primitive]:
    """× 斜め十字(記号の外形いっぱいに広がる)。"""
    return [
        _line(-r, -r, r, r),
        _line(-r, r, r, -r),
    ]


def _inner_cross(r: float) -> List[Primitive]:
    """円の内側に収まる斜め十字(円周上まで)。"""
    d = r * _DIAG
    return [
        _line(-d, -d, d, d),
        _line(-d, d, d, -d),
    ]


def _plus(r: float) -> List[Primitive]:
    """十字線(縦横)。円周をわずかに越えて伸びる。"""
    e = r * 1.2
    return [
        _line(-e, 0.0, e, 0.0),
        _line(0.0, -e, 0.0, e),
    ]


def _circle_slash(r: float) -> List[Primitive]:
    """⊘ 丸 + 斜線 1 本。"""
    d = r * _DIAG
    return [_circle(r, False), _line(-d, -d, d, d)]


def _circle_dot(r: float) -> List[Primitive]:
    """⊙ 丸 + 中心の点。"""
    return [_circle(r, False), _circle(r * 0.22, True)]


def _circle_cross(r: float) -> List[Primitive]:
    """⊗ 丸 + 内側の ×。"""
    return [_circle(r, False), *_inner_cross(r)]


def _double_circle(r: float) -> List[Primitive]:
    """◎ 二重丸。"""
    return [_circle(r, False), _circle(r * 0.5, False)]


def _circle_plus(r: float) -> List[Primitive]:
    """⊕ 丸 + 十字線。"""
    return [_circle(r, False), *_plus(r)]


def _dot_plus(r: float) -> List[Primitive]:
    """●⊕ 塗り丸 + 十字線。"""
    return [_circle(r * 0.6, True), *_plus(r)]


# 呼び径 -> 記号の組み立て関数(引数は記号の半径 r = size/2)。
_SYMBOL_BUILDERS: Dict[int, Callable[[float], List[Primitive]]] = {
    10: _dot,
    13: _cross,
    16: _circle_slash,
    19: _dot,
    22: _open_circle,
    25: _circle_dot,
    29: _circle_cross,
    32: _double_circle,
    35: _circle_plus,
    38: _dot_plus,
    41: _circle_cross,
}


def _builder_for(nominal: int) -> Callable[[float], List[Primitive]]:
    """呼び径に対応する記号組み立て関数を返す(表外は最も近い標準径)。"""
    if nominal in _SYMBOL_BUILDERS:
        return _SYMBOL_BUILDERS[nominal]
    nearest = min(_SYMBOL_BUILDERS, key=lambda d: (abs(d - nominal), d))
    return _SYMBOL_BUILDERS[nearest]


def build_symbol(nominal: int, size: float) -> List[Primitive]:
    """呼び径 ``nominal`` の断面表示記号を外径 ``size`` で組み立てる。

    記号は中心(0, 0)を基準にした線・円のプリミティブのリスト。
    ``size`` は記号の外径(``呼び径 × MarkScale``)で、半径 ``r = size/2``。
    """
    return _builder_for(nominal)(size / 2.0)
