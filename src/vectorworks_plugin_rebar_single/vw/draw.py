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

from typing import Any, Sequence

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


# 塗りパターン: 1=実塗り(前景色ベタ)、0=塗りなし。記号の ●/○ は意味が
# 塗り/輪郭で決まるため、クラス塗りに関わらず明示する。
SOLID_FILL_PATTERN = 1
NO_FILL_PATTERN = 0


def draw_line_2d(
    start: Sequence[float], end: Sequence[float], class_name: str
) -> Any:
    """2D の線(平面投影・平面記号の線)を描き、ハンドルを返す。"""
    vs.MoveTo((start[0], start[1]))
    vs.LineTo((end[0], end[1]))
    handle = vs.LNewObj()
    if not _null(handle):
        set_class_with_attributes(handle, class_name)
    return handle


def draw_circle_2d(
    center: Sequence[float], radius: float, filled: bool, class_name: str
) -> Any:
    """2D の円(平面記号の ○ ・●)を描き、ハンドルを返す。

    記号の意味に合わせ、``filled=True`` は実塗り(●)、``filled=False`` は
    塗りなしの輪郭(○)にする(クラス塗りに関わらず明示)。
    """
    cx, cy = center[0], center[1]
    vs.Oval((cx - radius, cy + radius), (cx + radius, cy - radius))
    handle = vs.LNewObj()
    if not _null(handle):
        set_class_with_attributes(handle, class_name)
        try:
            vs.SetFPat(handle, SOLID_FILL_PATTERN if filled else NO_FILL_PATTERN)
        except Exception:
            pass
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
    """原点系の塗り円プロファイル(``vs.Oval``, 閉じた面)を作りハンドルを返す。

    閉じた塗り形状のため、押し出すとソリッド(切断=塗り円)になる。
    """
    vs.Oval((cx - radius, cy + radius), (cx + radius, cy - radius))
    return vs.LNewObj()


def _circle_curve_profile(cx: float, cy: float, radius: float) -> Any:
    """輪郭だけの円プロファイル(``vs.ArcByCenter`` 360°)を作りハンドルを返す。

    開いた曲線のため、押し出すと筒面(切断=輪郭線)になる。
    """
    vs.ArcByCenter(cx, cy, radius, 0.0, 360.0)
    return vs.LNewObj()


def _line_profile(
    start: Sequence[float], end: Sequence[float]
) -> Any:
    """直線プロファイル(``vs.MoveTo``/``vs.LineTo``)を作りハンドルを返す。

    開いた線のため、押し出すと平面(切断=線)になる。
    """
    vs.MoveTo((start[0], start[1]))
    vs.LineTo((end[0], end[1]))
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


def draw_symbol_line(
    start: Sequence[float],
    end: Sequence[float],
    path: Sequence[Sequence[float]],
    class_name: str,
) -> Any:
    """線プロファイルをパスに沿って押し出す(記号の × ・+ ・斜線)。

    開いた線を押し出すと平面(帯)になり、断面の切断で線として現れる。
    """
    solid = _extrude(path, _line_profile(start, end))
    if not _null(solid):
        set_class_with_attributes(solid, class_name)
    return solid


def draw_symbol_circle(
    center: Sequence[float],
    radius: float,
    filled: bool,
    path: Sequence[Sequence[float]],
    class_name: str,
) -> Any:
    """円プロファイルをパスに沿って押し出す(記号の ○ ・●)。

    ``filled=True`` は塗り円(``vs.Oval``)を押し出してソリッド(切断=塗り円)、
    ``filled=False`` は輪郭円(``vs.ArcByCenter`` 360°)を押し出して筒面
    (切断=輪郭線)にする。
    """
    if filled:
        profile = _oval_profile(center[0], center[1], radius)
    else:
        profile = _circle_curve_profile(center[0], center[1], radius)
    solid = _extrude(path, profile)
    if not _null(solid):
        set_class_with_attributes(solid, class_name)
    return solid
