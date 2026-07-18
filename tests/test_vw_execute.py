"""描画フェーズ (vw.execute_document) のテスト。vs をモックし手書きの命令で検証する。"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

from vectorworks_plugin_rebar_single.document import DOCUMENT_VERSION

PIO_HANDLE = 'PIO_HANDLE'


def make_document() -> Dict[str, Any]:
    return {
        'version': DOCUMENT_VERSION,
        'solid': {
            'diameter': 14.0,
            'path': [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]],
        },
        'plan_lines': [{'start': [0.0, 0.0], 'end': [1000.0, 0.0]}],
        'cut_marks': [
            {
                'target': 'front_back',
                'primitives': [
                    {
                        'kind': 'circle',
                        'center': [0.0, 0.0],
                        'radius': 26.0,
                        'filled': False,
                    },
                    {'kind': 'line', 'start': [-18.0, -18.0], 'end': [18.0, 18.0]},
                    {'kind': 'line', 'start': [-18.0, 18.0], 'end': [18.0, -18.0]},
                ],
            },
            {
                'target': 'left_right',
                'primitives': [
                    {
                        'kind': 'circle',
                        'center': [0.0, 0.0],
                        'radius': 26.0,
                        'filled': True,
                    }
                ],
            },
        ],
    }


def _make_vs_mock() -> MagicMock:
    vs_mock = MagicMock()
    null_handle = object()
    vs_mock.Handle.return_value = null_handle
    handles: List[str] = []

    def new_obj() -> str:
        handles.append(f'OBJ_{len(handles)}')
        return handles[-1]

    vs_mock.LNewObj.side_effect = new_obj
    vs_mock.Set2DComponentGroup.return_value = True
    vs_mock.GetClass.return_value = 'PIOクラス'
    return vs_mock


def _load(vs_mock: MagicMock) -> Any:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_rebar_single.vw.component as vw_component
        import vectorworks_plugin_rebar_single.vw.draw as vw_draw
        import vectorworks_plugin_rebar_single.vw as vw
        importlib.reload(vw_draw)
        importlib.reload(vw_component)
        importlib.reload(vw)
        return vw


class TestExecuteDocument:
    def test_counts(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        result = vw.execute_document(make_document(), PIO_HANDLE)

        assert result['solid'] == 1
        assert result['plan_lines'] == 1
        assert result['cut_marks'] == 2  # front_back + left_right

    def test_top_plan_view_fixed_to_top(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        vs_mock.SetTopPlan2DComp.assert_called_once_with(PIO_HANDLE, 0)

    def test_solid_drawn_via_extrude(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # 断面円のパス押し出しソリッドを生成する(フォールバックのポリラインでない)
        assert vs_mock.CreateExtrudeAlongPath.called
        assert vs_mock.CreateNurbsCurve.called
        assert not vs_mock.Poly3D.called

    def test_solid_falls_back_to_polyline(self) -> None:
        vs_mock = _make_vs_mock()
        del vs_mock.CreateExtrudeAlongPath
        vw = _load(vs_mock)

        counts = vw.execute_document(make_document(), PIO_HANDLE)

        # 押し出しが使えない環境では 3D ポリラインで描く
        assert vs_mock.Poly3D.called
        assert vs_mock.OpenPoly.called
        assert counts['solid'] == 1

    def test_solid_falls_back_on_null_solid(self) -> None:
        vs_mock = _make_vs_mock()
        # 押し出しが NULL を返す(生成失敗)場合もポリラインへ
        vs_mock.CreateExtrudeAlongPath.return_value = vs_mock.Handle.return_value
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        assert vs_mock.Poly3D.called

    def test_plan_line_drawn_on_screen_plane(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # 平面線 (0,0)->(1000,0)
        starts = {c.args[0] for c in vs_mock.MoveTo.call_args_list}
        assert (0.0, 0.0) in starts
        # 2D 図形はすべて画面平面 (planar ref 0)
        for call in vs_mock.SetPlanarRef.call_args_list:
            assert call.args[1] == 0

    def test_filled_circle_gets_solid_fill(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # 塗り丸(●)はクラス塗りに関わらず実塗り(FPat=1)にする
        assert vs_mock.SetFPat.called
        assert all(c.args[1] == 1 for c in vs_mock.SetFPat.call_args_list)
        # left_right の塗り円 1 個だけ
        assert vs_mock.SetFPat.call_count == 1

    def test_circles_drawn_as_ovals(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # プロファイル円 1 + front_back 円 1 + left_right 円 1 = 3
        assert vs_mock.Oval.call_count == 3

    def test_cut_marks_assigned_to_components(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        calls = vs_mock.Set2DComponentGroup.call_args_list
        by_component = {c.args[2]: c.args for c in calls}
        # 前後の断面=6・左右の断面=9 の両方に設定する
        assert set(by_component) == {6, 9}
        assert by_component[6][0] == PIO_HANDLE
        assert by_component[6][1].startswith('OBJ_')

    def test_cut_groups_deleted_from_regen(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        # front_back・left_right の 2 グループを regen から削除する
        assert vs_mock.DelObject.call_count == 2
        # グループ化は 2 回(target ごと)
        assert vs_mock.BeginGroup.call_count == 2
        assert vs_mock.EndGroup.call_count == 2

    def test_empty_target_sets_null(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        doc = make_document()
        # left_right を削って空にする
        doc['cut_marks'] = [m for m in doc['cut_marks'] if m['target'] == 'front_back']
        vw.execute_document(doc, PIO_HANDLE)

        calls = vs_mock.Set2DComponentGroup.call_args_list
        by_component = {c.args[2]: c.args for c in calls}
        # 空の left_right(9)には NULL を設定して前回の残骸を消す
        assert by_component[9][1] is vs_mock.Handle.return_value

    def test_all_shapes_use_pio_class(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        vw.execute_document(make_document(), PIO_HANDLE)

        vs_mock.GetClass.assert_called_once_with(PIO_HANDLE)
        class_names = {c.args[1] for c in vs_mock.SetClass.call_args_list}
        assert class_names == {'PIOクラス'}

    def test_invalid_document_raises(self) -> None:
        vs_mock = _make_vs_mock()
        vw = _load(vs_mock)

        try:
            vw.execute_document({'version': 99}, PIO_HANDLE)
        except ValueError:
            pass
        else:
            raise AssertionError('ValueError が送出されるべき')
        assert not vs_mock.MoveTo.called
