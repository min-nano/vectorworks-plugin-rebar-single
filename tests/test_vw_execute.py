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
            {'kind': 'disk', 'center': [0.0, 0.0], 'radius': 26.0},
            {'kind': 'ring', 'center': [0.0, 0.0], 'outer': 26.0, 'inner': 20.0},
            {
                'kind': 'polygon',
                'points': [[-5.0, -5.0], [5.0, -5.0], [5.0, 5.0], [-5.0, 5.0]],
            },
        ],
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
    vs_mock.SubtractSolid.side_effect = lambda a, b: (0, unique('RING'))
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

        # 本体(1) + disk(1) + ring 外(1) + ring 内(1) + polygon(1) = 5 押し出し
        assert vs_mock.CreateExtrudeAlongPath.call_count == 5
        # 本体はポリラインへフォールバックしない
        assert not vs_mock.Poly3D.called

    def test_ring_uses_solid_subtraction(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        # ○ リングは外側から内側を引く
        assert vs_mock.SubtractSolid.call_count == 1

    def test_polygon_profile_uses_poly(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        # 帯(×)は塗り多角形プロファイル
        assert vs_mock.Poly.called

    def test_symbols_on_symbol_class_body_on_pio_class(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, SYMBOL_CLASS)

        classes = _class_calls(vs_mock)
        # 本体・平面線は PIO クラス、記号ソリッドは SymbolClass
        assert 'PIOクラス' in classes
        assert SYMBOL_CLASS in classes
        # 記号 3 プロファイル分が SymbolClass に割り当てられる
        assert classes.count(SYMBOL_CLASS) == 3

    def test_empty_symbol_class_falls_back_to_pio_class(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE, '')

        classes = _class_calls(vs_mock)
        # SymbolClass 未指定なら全て PIO クラス
        assert set(classes) == {'PIOクラス'}

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

        # 押し出しが使えない環境では本体は 3D ポリラインで描く
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
