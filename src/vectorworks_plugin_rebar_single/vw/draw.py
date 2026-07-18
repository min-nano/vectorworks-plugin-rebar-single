"""描画プリミティブ。vs だけに依存する。

命令セットの 2D 線・円(断面記号)と 3D ソリッド(断面円のパス押し出し)を
vs API で描画する。図形の作図クラスは **PIO 本体の描画クラス**(呼び出し側が
``vs.GetClass(pio)`` で取得して渡す)に揃え、描画属性(線の太さ・色・線種
等)はすべて by-class 属性に従わせる。クラス指定は PIO を扱う側(= PIO 本体
へのクラス割り当て)で管理するため、このパッケージは固有のクラス名を持た
ない。

3D ソリッドは ``CreateExtrudeAlongPath``(パス=NURBS 曲線、プロファイル=円)
で作る。断面ビューポートはこの 3D ソリッドをネイティブに切断できるため、
複雑な形状でも正しい位置に断面が出る。生成に失敗する環境では 3D
ポリラインへフォールバックする(3D ビューに鉄筋の芯線は出る)。
"""
from __future__ import annotations

from typing import Any, Sequence

import vs

# 画面平面(screen plane)の planar ref ID(vs のリファレンス: screen
# plane = 0)。2D コンポーネントのグループは画面平面のオブジェクトである
# 必要がある(``Set2DComponentGroup`` が断面コンポーネントのコンテナへ
# 移動できるようにするため)。
SCREEN_PLANE_REF = 0

# 塗り(●)を確実に実塗りにするための塗パターン。VW の FillPat で 1 は
# 実塗り(前景色ベタ)。塗り記号だけはクラス塗りに関わらず実塗りにする。
SOLID_FILL_PATTERN = 1

# NURBS パス曲線の次数。鉄筋の折れ(フック等)を丸めないよう線形補間
# (次数 1 = 折れ線)にする。
NURBS_DEGREE = 1


def set_screen_plane(handle: Any) -> None:
    """2D 図形を画面平面(screen plane)に置く。

    2D コンポーネント(Top/Plan・断面)のグループは画面平面のオブジェクト
    でないと ``Set2DComponentGroup`` が各コンポーネントのコンテナへ正しく
    移動できず、断面表現が平面ビューに漏れて表示される。``SetPlanarRef``
    が無い環境(VW 2018 以前)では何もしない。
    """
    try:
        setter = vs.SetPlanarRef
    except AttributeError:
        return
    setter(handle, SCREEN_PLANE_REF)


def set_class_with_attributes(handle: Any, class_name: str) -> None:
    """クラスを割り当て、描画属性をすべてクラス属性に従わせる。

    class_name が空(PIO のクラスを取得できない場合)はクラス割り当てを
    省くが、属性は by-class に設定する。``SetClass`` はクラスを割り当てる
    だけで各描画属性は by-instance の既定値のまま残るため、属性ごとの
    by-class 設定関数を個別に呼ぶ。
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
    """2D の線を描き、ハンドルを返す。

    2D コンポーネント(Top/Plan・断面)に振り分けられるよう画面平面
    (screen plane)に置く。
    """
    vs.MoveTo((start[0], start[1]))
    vs.LineTo((end[0], end[1]))
    handle = vs.LNewObj()
    if not _null(handle):
        set_screen_plane(handle)
        set_class_with_attributes(handle, class_name)
    return handle


def draw_circle_2d(
    center: Sequence[float], radius: float, filled: bool, class_name: str
) -> Any:
    """2D の円(断面記号の丸・塗り丸)を描き、ハンドルを返す。

    ``vs.Oval`` は外接矩形(左上・右下)で楕円を作る。断面記号の丸は
    真円のため半径から矩形を組み立てる。塗り丸(●)はクラス塗りに関わらず
    確実に実塗りにする(記号の意味が「塗り」のため)。
    """
    cx, cy = center[0], center[1]
    vs.Oval((cx - radius, cy + radius), (cx + radius, cy - radius))
    handle = vs.LNewObj()
    if not _null(handle):
        set_screen_plane(handle)
        set_class_with_attributes(handle, class_name)
        if filled:
            _set_solid_fill(handle)
    return handle


def _set_solid_fill(handle: Any) -> None:
    """塗り丸(●)を実塗りにする(クラス塗りに関わらず)。"""
    try:
        vs.SetFPat(handle, SOLID_FILL_PATTERN)
    except Exception:
        pass


def draw_poly_3d(
    vertices: Sequence[Sequence[float]], class_name: str
) -> Any:
    """3D ポリライン(ソリッド生成失敗時のフォールバック)を描く。

    ``OpenPoly`` はスクリプトで作るポリゴンの開閉モードを切り替える
    トグルのため、開モードを明示してから ``Poly3D`` で描く。
    """
    vs.OpenPoly()
    coordinates = [c for vertex in vertices for c in vertex]
    vs.Poly3D(*coordinates)
    handle = vs.LNewObj()
    if not _null(handle):
        set_class_with_attributes(handle, class_name)
    return handle


def _build_nurbs_path(vertices: Sequence[Sequence[float]]) -> Any:
    """3D パス頂点から NURBS 曲線(``CreateExtrudeAlongPath`` のパス)を作る。"""
    first = vertices[0]
    path = vs.CreateNurbsCurve(
        (first[0], first[1], first[2]), False, NURBS_DEGREE
    )
    if _null(path):
        return path
    for vertex in vertices[1:]:
        vs.AddVertex3D(path, (vertex[0], vertex[1], vertex[2]))
    return path


def _build_circle_profile(diameter: float) -> Any:
    """断面円のプロファイル(原点中心の真円)を作る。"""
    r = diameter / 2.0
    vs.Oval((-r, r), (r, -r))
    return vs.LNewObj()


def draw_solid_sweep(
    diameter: float, path: Sequence[Sequence[float]], class_name: str
) -> Any:
    """断面円をパスに沿って押し出した 3D ソリッドを描く。

    ``CreateExtrudeAlongPath``(パス=NURBS 曲線・プロファイル=円)で作る。
    生成に失敗した環境や例外時は 3D ポリライン(芯線)へフォールバックし、
    3D ビューに鉄筋が出るようにする。ハンドルを返す。
    """
    try:
        creator = vs.CreateExtrudeAlongPath
    except AttributeError:
        return draw_poly_3d(path, class_name)
    try:
        nurbs_path = _build_nurbs_path(path)
        profile = _build_circle_profile(diameter)
        if _null(nurbs_path) or _null(profile):
            raise RuntimeError('パスまたはプロファイルの生成に失敗しました')
        solid = creator(nurbs_path, profile)
        if _null(solid):
            raise RuntimeError('ソリッドの生成に失敗しました')
    except Exception:
        return draw_poly_3d(path, class_name)
    set_class_with_attributes(solid, class_name)
    return solid
