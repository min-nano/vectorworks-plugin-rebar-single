"""PIO コンテキスト読み取り (vw.pio) のテスト。vs をモックして検証する。"""
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

    def get_r_field(handle: str, record: str, field: str) -> str:
        assert handle == 'PIO_HANDLE'
        assert record == '鉄筋'
        return fields.get(field, '')

    vs_mock.GetRField.side_effect = get_r_field
    return vs_mock


def _load(vs_mock: MagicMock) -> Any:
    with patch.dict('sys.modules', {'vs': vs_mock}):
        import vectorworks_plugin_rebar_single.vw.pio as vw_pio
        importlib.reload(vw_pio)
        return vw_pio


FIELDS = {'Bar': 'D13', 'MarkScale': '4.0'}

PATH = [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0), (2000.0, 0.0, -500.0)]


class TestReadPioInput:
    def test_reads_params_and_path(self) -> None:
        vw_pio = _load(_make_vs_mock(FIELDS, PATH))

        result = vw_pio.read_pio_input()

        assert result is not None
        handle, params = result
        assert handle == 'PIO_HANDLE'
        assert params['bar'] == 'D13'
        assert params['mark_scale'] == 4.0
        assert params['path'] == [
            [0.0, 0.0, 0.0],
            [2000.0, 0.0, 0.0],
            [2000.0, 0.0, -500.0],
        ]

    def test_number_with_unit_suffix(self) -> None:
        fields = dict(FIELDS, MarkScale='4.0倍')
        vw_pio = _load(_make_vs_mock(fields, PATH))
        result = vw_pio.read_pio_input()
        assert result is not None
        assert result[1]['mark_scale'] == 4.0

    def test_unparsable_number_omitted(self) -> None:
        fields = dict(FIELDS, MarkScale='auto')
        vw_pio = _load(_make_vs_mock(fields, PATH))
        result = vw_pio.read_pio_input()
        assert result is not None
        assert 'mark_scale' not in result[1]

    def test_outside_pio_context_returns_none(self) -> None:
        vs_mock = _make_vs_mock(FIELDS, PATH)
        vs_mock.GetCustomObjectInfo.return_value = (False, '', None, None, None)
        vw_pio = _load(vs_mock)

        assert vw_pio.read_pio_input() is None

    def test_missing_path_returns_empty(self) -> None:
        vs_mock = _make_vs_mock(FIELDS, PATH)
        vs_mock.GetCustomObjectPath.return_value = vs_mock.Handle.return_value
        vw_pio = _load(vs_mock)

        result = vw_pio.read_pio_input()
        assert result is not None
        assert result[1]['path'] == []
