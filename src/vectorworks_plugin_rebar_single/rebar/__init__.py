"""フェーズ1: 配筋計算(1 本の鉄筋)。vs に一切依存しない。

PIO のパラメータとパス頂点(プレーンな dict、``vw.pio`` が組み立てる)
から、描くべき図形を JSON 直列化可能な命令セット(``document.py``)
として組み立てる。通常の Python 環境で単体実行・検証できる。

この PIO は 3D パス(鉄筋の芯線)に沿って 1 本の鉄筋を配置する:

- 本体: 鉄筋径(最外径)の円形断面をパスに沿って押し出した丸鋼ソリッド。
- 平面: 上から見たパスの投影図(2D 線)。
- 断面記号ソリッド: 呼び径に応じた表示記号(●/× 等)の断面形状をパスに
  沿って押し出したソリッド。断面ビューポートがネイティブに切断して記号
  として現れる(位置・向きに依存せず正しい位置に出る)。

入力 params のスキーマ:

    {
        "path": [[x, y, z], ...],   # 3D パス頂点 (PIO ローカル座標, mm)
        "bar": "D13",               # 呼び径
        "mark_scale": 4.0,          # 断面記号の大きさ = 呼び径 × 倍率
        "cut_height": 0.0           # 平面記号を出す切断高さ (z, mm)。省略時は
                                    # パスの z 範囲の中央
    }
"""
from __future__ import annotations

import math
from typing import Any, List, Mapping, Sequence

from ..document import DOCUMENT_VERSION, Document, PlanLineCommand, Profile
from .spec import BarSize, SpecError, parse_bar
from .symbol import build_symbol_profiles

__all__ = ['build_document', 'SpecError']

DEFAULT_BAR = 'D13'
DEFAULT_MARK_SCALE = 4.0

# パスが切断高さを横切る点の判定・重複統合に使う許容誤差 (mm)。
_EPS = 1e-6


def _float(params: Mapping[str, Any], key: str, default: float) -> float:
    value = params.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        raise SpecError(f'{key} を数値として解釈できません: {value!r}')


def _optional_float(params: Mapping[str, Any], key: str) -> float | None:
    """省略可能な数値パラメータを読む(欠落・解釈不能なら None)。"""
    if key not in params:
        return None
    try:
        return float(params[key])
    except (TypeError, ValueError):
        return None


def _text(params: Mapping[str, Any], key: str, default: str) -> str:
    value = params.get(key, default)
    return value if isinstance(value, str) else default


def _clean_path(path: Sequence[Sequence[float]]) -> List[List[float]]:
    """連続する重複点を除いた 3D パス頂点を返す。"""
    cleaned: List[List[float]] = []
    for vertex in path:
        point = [float(vertex[0]), float(vertex[1]), float(vertex[2])]
        if cleaned and _near3(cleaned[-1], point):
            continue
        cleaned.append(point)
    return cleaned


def _near3(a: Sequence[float], b: Sequence[float]) -> bool:
    return math.dist(a, b) < 1e-6


def _plan_lines(path: Sequence[Sequence[float]]) -> List[PlanLineCommand]:
    """上から見たパスの投影図(連続頂点を結ぶ 2D 線)。

    XY へ投影して退化する区間(縦筋のように上から見ると点になる区間)は
    描かない(平面には別途 2D 記号を出す)。
    """
    lines: List[PlanLineCommand] = []
    for start, end in zip(path, path[1:]):
        if math.hypot(end[0] - start[0], end[1] - start[1]) < 1e-6:
            continue
        lines.append(
            {
                'start': [start[0], start[1]],
                'end': [end[0], end[1]],
            }
        )
    return lines


def _default_cut_height(path: Sequence[Sequence[float]]) -> float:
    """切断高さ未指定時の既定値(パスの z 範囲の中央)。

    折れのないパスでも必ず 1 点で横切るよう、最小 z と最大 z の中間に
    取る。パス全体が同一 z(水平)なら切断面上に載るため記号は出ない。
    """
    zs = [float(v[2]) for v in path]
    return (min(zs) + max(zs)) / 2.0


def _plan_symbol_centers(
    path: Sequence[Sequence[float]], cut_height: float
) -> List[List[float]]:
    """パスが切断高さ ``cut_height`` を横切る XY 位置(複数可)。

    各区間について z = cut_height との交点を求め、その XY を返す。パスが
    折り返して切断面を複数回横切れば複数の点になる。両端が切断面上に載る
    水平区間(平面では線として出る)は記号を出さない。頂点共有などで生じる
    近接した重複点は 1 点に統合する。
    """
    h = cut_height
    centers: List[List[float]] = []
    for start, end in zip(path, path[1:]):
        za, zb = start[2] - h, end[2] - h
        # 両端が切断面上: 水平区間が面に載る。平面線として出るので記号なし。
        if abs(za) < _EPS and abs(zb) < _EPS:
            continue
        if abs(za) < _EPS:
            centers.append([float(start[0]), float(start[1])])
            continue
        if abs(zb) < _EPS:
            centers.append([float(end[0]), float(end[1])])
            continue
        if za * zb < 0:
            # 区間内で交差。t = (h - start.z) / (end.z - start.z) = za/(za-zb)
            # は za・zb が異符号のとき (0, 1) に入る。
            t = za / (za - zb)
            centers.append(
                [
                    float(start[0]) + t * (float(end[0]) - float(start[0])),
                    float(start[1]) + t * (float(end[1]) - float(start[1])),
                ]
            )
    return _dedupe_points(centers)


def _dedupe_points(points: Sequence[Sequence[float]]) -> List[List[float]]:
    """近接した点(切断面上の共有頂点で二重に出る等)を 1 点に統合する。"""
    deduped: List[List[float]] = []
    for point in points:
        if not any(
            math.hypot(point[0] - kept[0], point[1] - kept[1]) < _EPS
            for kept in deduped
        ):
            deduped.append([point[0], point[1]])
    return deduped


def build_document(params: Mapping[str, Any]) -> Document:
    """params から命令セット(ドキュメント)を組み立てる。

    仕様文字列の形式不正・パス不足は ``SpecError``(ユーザー向けメッセージ)
    を送出する。
    """
    raw_path = params.get('path')
    if not isinstance(raw_path, list) or not all(
        isinstance(v, (list, tuple)) and len(v) == 3 for v in raw_path
    ):
        raise SpecError('パス頂点を取得できません')
    path = _clean_path(raw_path)
    if len(path) < 2:
        raise SpecError('鉄筋のパスには 2 点以上の頂点が必要です')

    bar = parse_bar(_text(params, 'bar', DEFAULT_BAR))
    if bar is None:
        raise SpecError('鉄筋径(Bar)を入力してください')

    mark_scale = _float(params, 'mark_scale', DEFAULT_MARK_SCALE)
    if mark_scale <= 0:
        mark_scale = DEFAULT_MARK_SCALE

    profiles: List[Profile] = build_symbol_profiles(
        bar.nominal, bar.nominal * mark_scale
    )

    cut_height = _optional_float(params, 'cut_height')
    if cut_height is None:
        cut_height = _default_cut_height(path)

    return {
        'version': DOCUMENT_VERSION,
        'path': path,
        'tube_diameter': bar.outer,
        'plan_lines': _plan_lines(path),
        'symbol_profiles': profiles,
        'plan_symbol_centers': _plan_symbol_centers(path, cut_height),
    }
