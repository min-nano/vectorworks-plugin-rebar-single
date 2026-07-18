"""描画フェーズ (vw.execute_document) のテスト。vs をモックし手書きの命令で検証する。"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from vectorworks_plugin_rebar_single.document import DOCUMENT_VERSION

PIO_HANDLE = 'PIO_HANDLE'
SYMBOL_CLASS = '鉄筋-断面記号'


def make_document() -> Dict[str, Any]:
    return {
        'version': DOCUMENT_VERSION,
        'path': [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]],
        'tube_diameter': 14.0,
        'plan_lines': [{'start': [0.0, 0.0], 'end': [1000.0, 0.0]}],
        'symbol_profiles': [
            {'kind': 'circle', 'center': [0.0, 0.0], 'radius': 26.0, 'filled': False},
            {'kind': 'circle', 'center': [0.0, 0.0], 'radius': 6.0, 'filled': True},
            {'kind': 'line', 'start': [-18.0, -18.0], 'end': [18.0, 18.0]},
        ],
        'plan_symbol_centers': [[500.0, 0.0]],
    }


def _make_vs_mock() -> MagicMock:
    vs_mock = MagicMock()
    null_handle = object()
    vs_mock.Handle.return_value = null_handle

    counter = {'n': 0}

    def unique(prefix: str) -> str:
        counter['n'] += 1
        return f'{prefix}_{counter["n"]}'

    vs_mock.LNewObj.side_effect = lambda: unique('OBJ')
    vs_mock.CreateNurbsCurve.side_effect = lambda *a: unique('NURBS')
    vs_mock.CreateExtrudeAlongPath.side_effect = lambda *a: unique('SOLID')
    vs_mock.GetClass.return_value = 'PIOクラス'
    return vs_mock


def _load(vs_mock: MagicMock) -> Any:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_rebar_single.vw.draw as vw_draw
        import vectorworks_plugin_rebar_single.vw as vw
        importlib.reload(vw_draw)
        importlib.reload(vw)
        return vw


def _class_calls(vs_mock: MagicMock) -> List[str]:
    return [c.args[1] for c in vs_mock.SetClass.call_args_list]


class TestExecuteDocument:
    def test_counts(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        result = vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        assert result['tube'] == 1
        assert result['plan_lines'] == 1
        assert result['symbol_profiles'] == 3

    def test_tube_and_symbols_extruded(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        # 本体(1) + 記号 3 プロファイル(1 ずつ) = 4 押し出し
        assert vs_mock.CreateExtrudeAlongPath.call_count == 4
        assert not vs_mock.Poly3D.called

    def test_outline_circle_uses_arc_for_3d_sweep(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        # 3D の輪郭円(○)は ArcByCenter 360°(押し出すと筒面=切断が輪郭線)
        assert vs_mock.ArcByCenter.called
        arc = vs_mock.ArcByCenter.call_args
        assert arc.args[3] == 0.0 and arc.args[4] == 360.0

    def test_3d_line_profile_uses_moveto_at_origin(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        # 3D 記号の線(×)は原点中心の MoveTo/LineTo プロファイル
        starts = {c.args[0] for c in vs_mock.MoveTo.call_args_list}
        assert (-18.0, -18.0) in starts

    def test_plan_symbol_drawn_at_center(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        # 平面 2D 記号はプロファイルを plan_symbol_centers=(500,0) へ平行移動
        # して描く。記号の線(-18,-18) は (482,-18) になる
        starts = {c.args[0] for c in vs_mock.MoveTo.call_args_list}
        assert (482.0, -18.0) in starts
        # 平面 2D の円(○ 輪郭・● 塗り)は Oval + SetFPat(0/1)
        assert vs_mock.SetFPat.called
        fpats = {c.args[1] for c in vs_mock.SetFPat.call_args_list}
        assert fpats == {0, 1}  # 輪郭=0・塗り=1

    def test_plan_symbol_drawn_at_each_center(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        document = make_document()
        # 折り返しで 2 か所を横切る場合を模擬(記号位置が 2 つ)
        document['plan_symbol_centers'] = [[100.0, 0.0], [900.0, 0.0]]
        vw.execute_document(document, PIO_HANDLE, SYMBOL_CLASS)

        # 記号の線(-18,-18) が両方の位置へ平行移動して描かれる
        starts = {c.args[0] for c in vs_mock.MoveTo.call_args_list}
        assert (82.0, -18.0) in starts
        assert (882.0, -18.0) in starts

    def test_no_plan_symbol_when_no_center(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        document = make_document()
        # パスが切断高さを横切らない場合は平面記号を描かない
        document['plan_symbol_centers'] = []
        vw.execute_document(document, PIO_HANDLE, SYMBOL_CLASS)

        # 平面記号の Oval(円記号)は描かれない(SetFPat も呼ばれない)
        assert not vs_mock.SetFPat.called

    def test_symbols_on_symbol_class_body_on_pio_class(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        classes = _class_calls(vs_mock)
        assert 'PIOクラス' in classes
        # 記号 3 プロファイル分が SymbolClass に割り当てられる
        assert classes.count(SYMBOL_CLASS) == 3

    def test_empty_symbol_class_falls_back_to_pio_class(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, '')

        assert set(_class_calls(vs_mock)) == {'PIOクラス'}

    def test_plan_line_drawn(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        starts = {c.args[0] for c in vs_mock.MoveTo.call_args_list}
        assert (0.0, 0.0) in starts

    def test_tube_falls_back_to_polyline(self) -> None:
        vs_mock = _make_vs_mock()
        del vs_mock.CreateExtrudeAlongPath
        vw = _load(vs_mock)

        result = vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        assert vs_mock.Poly3D.called
        assert result['tube'] == 1

    def test_invalid_document_raises(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        try:
            vw.execute_document({'version': 99}, PIO_HANDLE, SYMBOL_CLASS)
        except ValueError:
            pass
        else:
            raise AssertionError('ValueError が送出されるべき')
        assert not vs_mock.CreateExtrudeAlongPath.called
