"""鉄筋径の仕様文字列のパース。vs に依存しない。

VectorWorks の OIP でユーザーが入力する呼び径の仕様文字列を解釈する:

- ``D13`` / ``13`` → 呼び径 13(異形鉄筋)。

全角文字(Ｄ・全角数字)での入力にも耐えるよう、パース前に NFKC 正規化で
半角へ揃える。空文字・空白のみの入力は「指定なし」として ``None`` を返し、
形式不正は ``SpecError``(ValueError) を送出する(呼び出し側がメッセージ
表示に使う)。

配筋標準図(KSE 2008)の最外径表に基づき、呼び径から最外径(3D ソリッドの
断面円の直径)を引く。表にない呼び径は最も近い標準呼び径の最外径で近似
する(呼び径そのものが小さすぎる/大きすぎる場合の保険)。
"""
from __future__ import annotations

import re
import unicodedata
from typing import NamedTuple, Optional

# 配筋標準図(KSE 2008)の「鉄筋の表示記号及び最外径」表。
# 呼び径 (mm) -> 最外径 D (mm)。
OUTER_DIAMETER = {
    10: 11.0,
    13: 14.0,
    16: 18.0,
    19: 21.0,
    22: 25.0,
    25: 28.0,
    29: 33.0,
    32: 36.0,
    35: 40.0,
    38: 43.0,
    41: 46.0,
}


class SpecError(ValueError):
    """鉄筋仕様文字列の形式不正。メッセージはユーザー向け(日本語)。"""


class BarSize(NamedTuple):
    """鉄筋径の仕様 (例 D13)。

    ``nominal`` は呼び径(表示記号の選択・記号の大きさに使う)、``outer``
    は最外径(3D ソリッドの断面円の直径)。
    """

    nominal: int   # 呼び径 (mm)
    outer: float   # 最外径 (mm)


_NUMBER = r'\d+(?:\.\d+)?'
_BAR_RE = re.compile(rf'^D?\s*({_NUMBER})$', re.IGNORECASE)


def _normalize(text: str) -> str:
    """全角英数字を半角へ正規化し、前後の空白を除く。"""
    return unicodedata.normalize('NFKC', text).strip()


def outer_diameter(nominal: int) -> float:
    """呼び径から最外径(mm)を引く。表にない径は最も近い標準径で近似する。"""
    if nominal in OUTER_DIAMETER:
        return OUTER_DIAMETER[nominal]
    nearest = min(OUTER_DIAMETER, key=lambda d: (abs(d - nominal), d))
    # 表外の径は「呼び径の比率で最寄りの最外径をスケール」して近似する
    # (呼び径 == 0 は _BAR_RE で弾かれるため到達しない)。
    return OUTER_DIAMETER[nearest] * (nominal / nearest)


def parse_bar(text: str) -> Optional[BarSize]:
    """``D13`` / ``13`` 形式(呼び径)をパースする。空入力は None。"""
    normalized = _normalize(text)
    if not normalized:
        return None
    match = _BAR_RE.match(normalized)
    if match is None:
        raise SpecError(f'鉄筋径を解釈できません(D13 の形式): {text!r}')
    value = float(match.group(1))
    if value <= 0:
        raise SpecError(f'鉄筋径は正の値にしてください: {text!r}')
    nominal = int(round(value))
    return BarSize(nominal, outer_diameter(nominal))
