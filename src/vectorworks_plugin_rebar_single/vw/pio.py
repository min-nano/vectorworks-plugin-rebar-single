"""PIO コンテキストの読み取り。vs だけに依存する。

リセット中の PIO 自身の情報(``vs.GetCustomObjectInfo``)から、
パラメータ(レコードフィールド)と 3D パス頂点を読み取り、
配筋計算フェーズ(``rebar.build_document``)へ渡すプレーンな
dict(JSON 直列化可能)を組み立てる。

パラメータ(レコードフィールド)名は VectorWorks 側で登録する
プラグインのパラメータ名と一致させる必要がある(README の登録手順
参照)。名前はこのモジュール冒頭の定数に集約している。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import vs

# PIO のパラメータ(レコードフィールド)名。VectorWorks 側のプラグイン
# 定義と一致させること。
PARAM_BAR = 'Bar'
PARAM_MARK_SCALE = 'MarkScale'

# 数値フィールドの文字列から数値部分を取り出す(単位付き "13.0mm" や
# 桁区切りを許容する)
_NUMBER_RE = re.compile(r'-?\d+(?:\.\d+)?')


def _field(record_name: str, handle: Any, field: str) -> str:
    """レコードフィールドを文字列で読む。失敗時は空文字。"""
    try:
        value = vs.GetRField(handle, record_name, field)
    except Exception:
        return ''
    return value if isinstance(value, str) else ''


def _number(text: str) -> Optional[float]:
    """数値フィールドの文字列を float にする(単位表記を無視)。"""
    match = _NUMBER_RE.search(text.replace(',', ''))
    return float(match.group(0)) if match else None


def read_path(pio_handle: Any) -> List[List[float]]:
    """PIO のパス頂点(ローカル座標)を読み取る。

    3D パス図形のパスは 3D 基準の多角形(または NURBS 曲線)で、
    ``GetPolyPt3D`` は 0 始まりのインデックスで頂点を返す。
    """
    path_handle = vs.GetCustomObjectPath(pio_handle)
    if path_handle == vs.Handle(0):
        return []
    count = vs.GetVertNum(path_handle)
    path: List[List[float]] = []
    for index in range(count):
        x, y, z = vs.GetPolyPt3D(path_handle, index)
        path.append([float(x), float(y), float(z)])
    return path


def read_pio_input() -> Optional[Tuple[Any, Dict[str, Any]]]:
    """リセット中の PIO のハンドルと params dict を返す。

    PIO コンテキスト外(``GetCustomObjectInfo`` が False)の場合は None。
    数値フィールドが解釈できない場合はキーを省き、配筋計算フェーズの
    既定値に委ねる。
    """
    ok, record_name, pio_handle, _record, _wall = vs.GetCustomObjectInfo()
    if not ok:
        return None

    def field(name: str) -> str:
        return _field(record_name, pio_handle, name)

    params: Dict[str, Any] = {
        'path': read_path(pio_handle),
        'bar': field(PARAM_BAR),
    }
    mark_scale = _number(field(PARAM_MARK_SCALE))
    if mark_scale is not None:
        params['mark_scale'] = mark_scale
    return pio_handle, params
