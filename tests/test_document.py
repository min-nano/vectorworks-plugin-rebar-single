"""命令セットの検証 (document.validate_document) のテスト。vs 非依存。"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from vectorworks_plugin_rebar_single.document import (
    DOCUMENT_VERSION,
    validate_document,
)


def _valid() -> Dict[str, Any]:
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


class TestValidateDocument:
    def test_valid_passes(self) -> None:
        assert validate_document(_valid()) is not None

    def test_not_dict(self) -> None:
        with pytest.raises(ValueError):
            validate_document([])

    def test_wrong_version(self) -> None:
        doc = _valid()
        doc['version'] = 1
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_short_path(self) -> None:
        doc = _valid()
        doc['path'] = [[0.0, 0.0, 0.0]]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_bad_path_vertex(self) -> None:
        doc = _valid()
        doc['path'] = [[0.0, 0.0], [1.0, 1.0]]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_bad_tube_diameter(self) -> None:
        doc = _valid()
        doc['tube_diameter'] = -1.0
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_plan_lines_not_list(self) -> None:
        doc = _valid()
        doc['plan_lines'] = 'nope'
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_profiles_not_list(self) -> None:
        doc = _valid()
        doc['symbol_profiles'] = {}
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_circle_bad_radius(self) -> None:
        doc = _valid()
        doc['symbol_profiles'][0]['radius'] = 0
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_circle_missing_filled(self) -> None:
        doc = _valid()
        del doc['symbol_profiles'][0]['filled']
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_line_bad_point(self) -> None:
        doc = _valid()
        doc['symbol_profiles'][2]['start'] = [1.0]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_profile_bad_kind(self) -> None:
        doc = _valid()
        doc['symbol_profiles'][0]['kind'] = 'star'
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_empty_profiles_ok(self) -> None:
        # 記号なし(空リスト)は許容する
        doc = _valid()
        doc['symbol_profiles'] = []
        assert validate_document(doc) is not None

    def test_plan_symbol_centers_required(self) -> None:
        doc = _valid()
        del doc['plan_symbol_centers']
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_plan_symbol_centers_not_list(self) -> None:
        doc = _valid()
        doc['plan_symbol_centers'] = [500.0, 0.0]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_plan_symbol_centers_bad_point(self) -> None:
        doc = _valid()
        doc['plan_symbol_centers'] = [[1.0, 2.0, 3.0]]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_plan_symbol_centers_empty_ok(self) -> None:
        # パスが切断高さを横切らない場合は空(平面に記号なし)を許容する
        doc = _valid()
        doc['plan_symbol_centers'] = []
        assert validate_document(doc) is not None

    def test_plan_symbol_centers_multiple_ok(self) -> None:
        # 折り返しで複数の記号位置になる場合を許容する
        doc = _valid()
        doc['plan_symbol_centers'] = [[100.0, 0.0], [900.0, 0.0]]
        assert validate_document(doc) is not None
