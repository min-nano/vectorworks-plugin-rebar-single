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
            {'kind': 'disk', 'center': [0.0, 0.0], 'radius': 26.0},
            {'kind': 'ring', 'center': [0.0, 0.0], 'outer': 26.0, 'inner': 20.0},
            {
                'kind': 'polygon',
                'points': [[-5.0, -5.0], [5.0, -5.0], [5.0, 5.0], [-5.0, 5.0]],
            },
        ],
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

    def test_disk_bad_radius(self) -> None:
        doc = _valid()
        doc['symbol_profiles'][0]['radius'] = 0
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_ring_inner_ge_outer(self) -> None:
        doc = _valid()
        doc['symbol_profiles'][1]['inner'] = 30.0
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_polygon_too_few_points(self) -> None:
        doc = _valid()
        doc['symbol_profiles'][2]['points'] = [[0.0, 0.0], [1.0, 1.0]]
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
