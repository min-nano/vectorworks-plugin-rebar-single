"""配筋計算フェーズ (rebar.build_document) のテスト。vs 非依存。"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from vectorworks_plugin_rebar_single.document import (
    DOCUMENT_VERSION,
    KIND_CIRCLE,
    KIND_LINE,
    validate_document,
)
from vectorworks_plugin_rebar_single.rebar import SpecError, build_document


def _params(**overrides: Any) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        'path': [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]],
        'bar': 'D13',
        'mark_scale': 4.0,
    }
    params.update(overrides)
    return params


class TestBuildDocument:
    def test_produces_valid_document(self) -> None:
        doc = build_document(_params())
        validate_document(doc)
        assert doc['version'] == DOCUMENT_VERSION

    def test_tube_uses_outer_diameter(self) -> None:
        # D13 の最外径は 14mm
        doc = build_document(_params(bar='D13'))
        assert doc['tube_diameter'] == 14.0
        assert doc['path'] == [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]]

    def test_plan_lines_are_path_projection(self) -> None:
        doc = build_document(
            _params(path=[[0.0, 0.0, 0.0], [500.0, 0.0, -100.0], [500.0, 300.0, -100.0]])
        )
        assert doc['plan_lines'] == [
            {'start': [0.0, 0.0], 'end': [500.0, 0.0]},
            {'start': [500.0, 0.0], 'end': [500.0, 300.0]},
        ]

    def test_plan_symbol_center_at_cut_height_crossing(self) -> None:
        # 斜めのパスが指定した切断高さ(z=-200)を横切る XY 位置に記号を出す
        doc = build_document(
            _params(
                path=[[0.0, 0.0, 0.0], [1000.0, 0.0, -400.0]], cut_height=-200.0
            )
        )
        assert doc['plan_symbol_centers'] == [[500.0, 0.0]]

    def test_default_cut_height_is_mid_z_range(self) -> None:
        # 切断高さ未指定なら z 範囲の中央(0 と -400 の中間 -200)で横切る
        doc = build_document(
            _params(path=[[0.0, 0.0, 0.0], [1000.0, 0.0, -400.0]])
        )
        assert doc['plan_symbol_centers'] == [[500.0, 0.0]]

    def test_horizontal_bar_at_cut_height_has_no_symbol(self) -> None:
        # 切断面に載る水平区間は平面では線(plan_lines)で出るので記号は出さない
        doc = build_document(
            _params(path=[[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]], cut_height=0.0)
        )
        assert doc['plan_symbol_centers'] == []

    def test_bar_not_crossing_cut_height_has_no_symbol(self) -> None:
        # パスが切断高さを横切らなければ平面に記号は出ない
        doc = build_document(
            _params(
                path=[[0.0, 0.0, 0.0], [1000.0, 0.0, -400.0]], cut_height=500.0
            )
        )
        assert doc['plan_symbol_centers'] == []

    def test_folded_path_yields_multiple_symbols(self) -> None:
        # 折り返して切断高さ(z=0)を 2 回横切るパスは記号位置が 2 つになる
        doc = build_document(
            _params(
                path=[
                    [0.0, 0.0, 10.0],
                    [50.0, 0.0, -10.0],
                    [100.0, 0.0, 10.0],
                ],
                cut_height=0.0,
            )
        )
        assert doc['plan_symbol_centers'] == [[25.0, 0.0], [75.0, 0.0]]

    def test_vertical_bar_has_no_plan_line_but_has_symbol(self) -> None:
        # 縦筋(XY が同一・Z のみ変化)は投影線が退化するので描かず、
        # 平面には切断高さを横切る位置の 2D 記号で示す
        doc = build_document(
            _params(bar='D13', path=[[100.0, 200.0, 0.0], [100.0, 200.0, -400.0]])
        )
        assert doc['plan_lines'] == []
        # 既定切断高さ(-200)で縦筋が横切る XY (100, 200)
        assert doc['plan_symbol_centers'] == [[100.0, 200.0]]
        assert doc['symbol_profiles']  # 記号は残る(平面・断面で使う)

    def test_shared_vertex_on_cut_plane_dedupes(self) -> None:
        # 頂点が切断面上に載る交差は隣接 2 区間で二重に出ないよう 1 点に統合
        doc = build_document(
            _params(
                path=[
                    [0.0, 0.0, 10.0],
                    [50.0, 0.0, 0.0],
                    [100.0, 0.0, -10.0],
                ],
                cut_height=0.0,
            )
        )
        assert doc['plan_symbol_centers'] == [[50.0, 0.0]]

    def test_d13_symbol_is_two_lines(self) -> None:
        # D13 は × (線 2 本)
        doc = build_document(_params(bar='D13'))
        profiles = doc['symbol_profiles']
        assert all(p['kind'] == KIND_LINE for p in profiles)
        assert len(profiles) == 2

    def test_symbol_profiles_present(self) -> None:
        # D22 は ○ (輪郭の円)
        doc = build_document(_params(bar='D22'))
        assert doc['symbol_profiles']  # 空でない
        assert doc['symbol_profiles'][0]['kind'] == KIND_CIRCLE
        assert doc['symbol_profiles'][0]['filled'] is False

    def test_mark_scale_affects_symbol_size(self) -> None:
        small = build_document(_params(bar='D22', mark_scale=2.0))
        large = build_document(_params(bar='D22', mark_scale=6.0))
        small_r = small['symbol_profiles'][0]['radius']
        large_r = large['symbol_profiles'][0]['radius']
        assert large_r == small_r * 3.0

    def test_empty_bar_raises(self) -> None:
        with pytest.raises(SpecError):
            build_document(_params(bar=''))

    def test_default_bar_when_missing(self) -> None:
        params = _params()
        del params['bar']
        doc = build_document(params)
        assert doc['tube_diameter'] == 14.0

    def test_default_mark_scale_when_missing(self) -> None:
        params = _params()
        del params['mark_scale']
        doc = build_document(params)
        assert doc['symbol_profiles']

    def test_non_positive_mark_scale_falls_back(self) -> None:
        doc = build_document(_params(bar='D22', mark_scale=-1.0))
        # 記号が正の半径で組み立つ(既定倍率へフォールバック)
        assert doc['symbol_profiles'][0]['radius'] > 0

    def test_duplicate_points_collapsed(self) -> None:
        doc = build_document(
            _params(path=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]])
        )
        assert len(doc['plan_lines']) == 1
        assert len(doc['path']) == 2

    def test_too_few_points_raises(self) -> None:
        with pytest.raises(SpecError):
            build_document(_params(path=[[0.0, 0.0, 0.0]]))

    def test_missing_path_raises(self) -> None:
        params = _params()
        del params['path']
        with pytest.raises(SpecError):
            build_document(params)

    def test_bad_bar_raises(self) -> None:
        with pytest.raises(SpecError):
            build_document(_params(bar='2-D16'))
