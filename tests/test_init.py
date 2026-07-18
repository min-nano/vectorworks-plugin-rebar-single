"""run() (PIO リセット全体のパイプライン) の統合テスト。vs をモックして検証する。"""
from __future__ import annotations

import importlib
from typing import Any, Dict, List, Tuple
from unittest.mock import MagicMock, patch


def _make_vs_mock(
    fields: Dict[str, str], path: List[Tuple[float, float, float]]
) -> MagicMock:
    vs_mock = MagicMock()
    null_handle = object()
    vs_mock.Handle.return_value = null_handle
    vs_mock.GetCustomObjectInfo.return_value = (
        True, '鉄筋', 'PIO_HANDLE', 'RECORD_HANDLE', 'WALL_HANDLE',
    )
    vs_mock.GetCustomObjectPath.return_value = 'PATH_HANDLE'
    vs_mock.GetVertNum.return_value = len(path)
    vs_mock.GetPolyPt3D.side_effect = lambda handle, index: path[index]
    vs_mock.GetRField.side_effect = (
        lambda handle, record, field: fields.get(field, '')
    )
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


def _run(vs_mock: MagicMock) -> None:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_rebar_single as package
        import vectorworks_plugin_rebar_single.vw.draw as vw_draw
        import vectorworks_plugin_rebar_single.vw.pio as vw_pio
        import vectorworks_plugin_rebar_single.vw as vw
        importlib.reload(vw_draw)
        importlib.reload(vw_pio)
        importlib.reload(vw)
        package.run()


FIELDS = {'Bar': 'D22', 'MarkScale': '4.0', 'SymbolClass': '鉄筋-断面記号'}

L_PATH = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (2000.0, 0.0, -400.0)]


class TestRun:
    def test_reset_draws_all_representations(self) -> None:
        vs_mock = _make_vs_mock(FIELDS, L_PATH)

        _run(vs_mock)

        # 本体丸鋼 + 記号ソリッドの押し出しが作られる
        assert vs_mock.CreateExtrudeAlongPath.called
        # 平面線(投影図)の 2D 図形が描かれる
        assert vs_mock.MoveTo.call_count > 0
        # 記号ソリッドは SymbolClass に割り当てられる
        classes = {c.args[1] for c in vs_mock.SetClass.call_args_list}
        assert '鉄筋-断面記号' in classes
        assert 'PIOクラス' in classes
        # 正常時はエラーメッセージを出さない
        assert not vs_mock.Message.called

    def test_spec_error_shows_message_without_crash(self) -> None:
        fields = dict(FIELDS, Bar='xxx')
        vs_mock = _make_vs_mock(fields, L_PATH)

        _run(vs_mock)

        assert vs_mock.Message.called
        message = vs_mock.Message.call_args.args[0]
        assert message.startswith('鉄筋: ')
        assert not vs_mock.MoveTo.called

    def test_short_path_shows_message(self) -> None:
        vs_mock = _make_vs_mock(FIELDS, [(0.0, 0.0, 0.0)])

        _run(vs_mock)

        assert vs_mock.Message.called

    def test_outside_pio_context_does_nothing(self) -> None:
        vs_mock = _make_vs_mock(FIELDS, L_PATH)
        vs_mock.GetCustomObjectInfo.return_value = (False, '', None, None, None)

        _run(vs_mock)

        assert not vs_mock.MoveTo.called
        assert not vs_mock.Message.called
