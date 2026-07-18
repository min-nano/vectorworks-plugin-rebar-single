"""描画プリミティブ。vs だけに依存する。

命令セットの 2D 線(平面投影)と 3D ソリッド(本体丸鋼・断面記号)を vs
API で描画する。作図クラスは呼び出し側が渡す(本体・平面線は PIO 本体の
描画クラス、記号ソリッドは ``SymbolClass`` で指定するクラス)。描画属性は
すべて by-class 属性に従わせる。

3D ソリッドは ``CreateExtrudeAlongPath``(パス=NURBS 曲線、プロファイル=
円/多角形)で作る。断面ビューポートはこのソリッドをネイティブに切断する
ため、位置・向きに依存せず正しい位置に断面が出る。
本体丸鋼は生成に失敗する環境では 3D ポリライン(芯線)へフォールバックする
(記号ソリッドはフォールバックせず、生成できなければ描かない)。
"""
from __future__ import annotations

from typing import Any, List, Sequence

import vs

# NURBS パス曲線の次数。鉄筋の折れ(フック等)を丸めないよう線形補間
# (次数 1 = 折れ線)にする。
NURBS_DEGREE = 1


def set_class_with_attributes(handle: Any, class_name: str) -> None:
    """クラスを割り当て、描画属性をすべてクラス属性に従わせる。

    class_name が空(クラスを取得できない場合)はクラス割り当てを省くが、
    属性は by-class に設定する。
    """
    if class_name:
        vs.SetClass(handle, class_name)
    vs.SetPenColorByClass(handle)
    vs.SetFillColorByClass(handle)
    vs.SetLWByClass(handle)
    vs.SetLSByClass(handle)
    vs.SetFPatByClass(handle)
    vs.SetMarkerByClass(handle)
    vs.SetOpacityByClass(handle)


def _null(handle: Any) -> bool:
    """ハンドルが NULL(生成失敗)かどうか。"""
    try:
        return handle == vs.Handle(0)
    except Exception:
        return handle is None


def draw_line_2d(
    start: Sequence[float], end: Sequence[float], class_name: str
) -> Any:
    """2D の線(平面投影)を描き、ハンドルを返す。"""
    vs.MoveTo((start[0], start[1]))
    vs.LineTo((end[0], end[1]))
    handle = vs.LNewObj()
    if not _null(handle):
        set_class_with_attributes(handle, class_name)
    return handle


def _build_nurbs_path(vertices: Sequence[Sequence[float]]) -> Any:
    """3D パス頂点から NURBS 曲線(``CreateExtrudeAlongPath`` のパス)を作る。

    押し出しはパスを消費するため、押し出しごとに新しいパスを作る。
    """
    first = vertices[0]
    path = vs.CreateNurbsCurve(
        (first[0], first[1], first[2]), False, NURBS_DEGREE
    )
    if _null(path):
        return path
    for vertex in vertices[1:]:
        vs.AddVertex3D(path, (vertex[0], vertex[1], vertex[2]))
    return path


def _oval_profile(cx: float, cy: float, radius: float) -> Any:
    """原点系の真円プロファイル(``vs.Oval``)を作りハンドルを返す。"""
    vs.Oval((cx - radius, cy + radius), (cx + radius, cy - radius))
    return vs.LNewObj()


def _polygon_profile(points: Sequence[Sequence[float]]) -> Any:
    """塗り多角形プロファイル(``vs.Poly``)を作りハンドルを返す。"""
    coordinates: List[float] = [c for point in points for c in point]
    vs.Poly(*coordinates)
    return vs.LNewObj()


def _extrude(path: Sequence[Sequence[float]], profile: Any) -> Any:
    """プロファイルをパスに沿って押し出したソリッドを返す(失敗時 NULL)。"""
    if _null(profile):
        return vs.Handle(0)
    nurbs = _build_nurbs_path(path)
    if _null(nurbs):
        return vs.Handle(0)
    try:
        return vs.CreateExtrudeAlongPath(nurbs, profile)
    except Exception:
        return vs.Handle(0)


def draw_poly_3d(vertices: Sequence[Sequence[float]], class_name: str) -> Any:
    """3D ポリライン(本体のソリッド生成失敗時のフォールバック)を描く。"""
    vs.OpenPoly()
    coordinates = [c for vertex in vertices for c in vertex]
    vs.Poly3D(*coordinates)
    handle = vs.LNewObj()
    if not _null(handle):
        set_class_with_attributes(handle, class_name)
    return handle


def draw_tube(
    diameter: float, path: Sequence[Sequence[float]], class_name: str
) -> Any:
    """本体丸鋼(最外径の円形断面のパス押し出し)を描く。

    生成に失敗する環境では 3D ポリライン(芯線)へフォールバックする。
    """
    try:
        vs.CreateExtrudeAlongPath
    except AttributeError:
        return draw_poly_3d(path, class_name)
    solid = _extrude(path, _oval_profile(0.0, 0.0, diameter / 2.0))
    if _null(solid):
        return draw_poly_3d(path, class_name)
    set_class_with_attributes(solid, class_name)
    return solid


def draw_symbol_disk(
    center: Sequence[float],
    radius: float,
    path: Sequence[Sequence[float]],
    class_name: str,
) -> Any:
    """塗り円プロファイルをパスに沿って押し出す(記号の ●・中心点)。"""
    solid = _extrude(path, _oval_profile(center[0], center[1], radius))
    if not _null(solid):
        set_class_with_attributes(solid, class_name)
    return solid


def draw_symbol_polygon(
    points: Sequence[Sequence[float]],
    path: Sequence[Sequence[float]],
    class_name: str,
) -> Any:
    """塗り多角形プロファイルをパスに沿って押し出す(記号の × 等の帯)。"""
    solid = _extrude(path, _polygon_profile(points))
    if not _null(solid):
        set_class_with_attributes(solid, class_name)
    return solid


def draw_symbol_ring(
    center: Sequence[float],
    outer: float,
    inner: float,
    path: Sequence[Sequence[float]],
    class_name: str,
) -> Any:
    """中空リング(○ 等)を外側ソリッドから内側ソリッドを引いて作る。"""
    outer_solid = _extrude(path, _oval_profile(center[0], center[1], outer))
    if _null(outer_solid):
        return outer_solid
    inner_solid = _extrude(path, _oval_profile(center[0], center[1], inner))
    if _null(inner_solid):
        # 中空にできない場合は塗り円で妥協する
        set_class_with_attributes(outer_solid, class_name)
        return outer_solid
    try:
        _status, ring = vs.SubtractSolid(outer_solid, inner_solid)
    except Exception:
        set_class_with_attributes(outer_solid, class_name)
        return outer_solid
    result = ring if not _null(ring) else outer_solid
    set_class_with_attributes(result, class_name)
    return result
