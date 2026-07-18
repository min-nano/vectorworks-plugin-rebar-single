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
                    {
                        'kind': 'line',
                        'start': [-18.0, -18.0],
                        'end': [18.0, 18.0],
                    },
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


class TestValidateDocument:
    def test_valid_passes(self) -> None:
        assert validate_document(_valid()) is not None

    def test_not_dict(self) -> None:
        with pytest.raises(ValueError):
            validate_document([])

    def test_wrong_version(self) -> None:
        doc = _valid()
        doc['version'] = 99
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_solid_missing(self) -> None:
        doc = _valid()
        del doc['solid']
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_solid_bad_diameter(self) -> None:
        doc = _valid()
        doc['solid']['diameter'] = -1.0
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_solid_short_path(self) -> None:
        doc = _valid()
        doc['solid']['path'] = [[0.0, 0.0, 0.0]]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_solid_bad_vertex(self) -> None:
        doc = _valid()
        doc['solid']['path'] = [[0.0, 0.0], [1.0, 1.0]]
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_plan_lines_not_list(self) -> None:
        doc = _valid()
        doc['plan_lines'] = 'nope'
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_cut_mark_bad_target(self) -> None:
        doc = _valid()
        doc['cut_marks'][0]['target'] = 'top'
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_cut_mark_empty_primitives(self) -> None:
        doc = _valid()
        doc['cut_marks'][0]['primitives'] = []
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_primitive_bad_kind(self) -> None:
        doc = _valid()
        doc['cut_marks'][0]['primitives'][0]['kind'] = 'rect'
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_circle_bad_radius(self) -> None:
        doc = _valid()
        doc['cut_marks'][1]['primitives'][0]['radius'] = 0
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_circle_missing_filled(self) -> None:
        doc = _valid()
        del doc['cut_marks'][1]['primitives'][0]['filled']
        with pytest.raises(ValueError):
            validate_document(doc)

    def test_line_bad_point(self) -> None:
        doc = _valid()
        doc['cut_marks'][0]['primitives'][1]['start'] = [1.0]
        with pytest.raises(ValueError):
            validate_document(doc)
