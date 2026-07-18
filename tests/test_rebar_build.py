"""配筋計算フェーズ (rebar.build_document) のテスト。vs 非依存。"""
from __future__ import annotations

from typing import Any, Dict

import pytest

from vectorworks_plugin_rebar_single.document import (
    DOCUMENT_VERSION,
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
        # 検証を通る命令セットであること
        validate_document(doc)
        assert doc['version'] == DOCUMENT_VERSION

    def test_solid_uses_outer_diameter(self) -> None:
        # D13 の最外径は 14mm
        doc = build_document(_params(bar='D13'))
        assert doc['solid']['diameter'] == 14.0
        assert doc['solid']['path'] == [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]]

    def test_plan_lines_are_path_projection(self) -> None:
        doc = build_document(
            _params(path=[[0.0, 0.0, 0.0], [500.0, 0.0, -100.0], [500.0, 300.0, -100.0]])
        )
        lines = doc['plan_lines']
        # 3 頂点 → 2 セグメント、XY へ投影
        assert lines == [
            {'start': [0.0, 0.0], 'end': [500.0, 0.0]},
            {'start': [500.0, 0.0], 'end': [500.0, 300.0]},
        ]

    def test_cut_marks_both_targets_same_shape(self) -> None:
        doc = build_document(_params())
        targets = {m['target'] for m in doc['cut_marks']}
        assert targets == {'front_back', 'left_right'}
        # 前後/左右で記号の「形」(種類・数)は同じ
        fb = next(m for m in doc['cut_marks'] if m['target'] == 'front_back')
        lr = next(m for m in doc['cut_marks'] if m['target'] == 'left_right')
        assert [p['kind'] for p in fb['primitives']] == [
            p['kind'] for p in lr['primitives']
        ]

    def test_symbol_placed_relative_to_first_vertex(self) -> None:
        # 記号は第 1 頂点を基準とした相対位置(重心 − 第 1 頂点)を投影して置く。
        # path=[(0,0,0),(1000,0,0)]: 第1頂点(0,0,0)・重心(500,0,0)
        # → 相対(500,0,0) → front_back=(X,Z)=(500,0)、left_right=(Y,Z)=(0,0)。
        doc = build_document(_params(bar='D22'))
        fb = next(m for m in doc['cut_marks'] if m['target'] == 'front_back')
        lr = next(m for m in doc['cut_marks'] if m['target'] == 'left_right')
        fb_circle = next(p for p in fb['primitives'] if p['kind'] != KIND_LINE)
        lr_circle = next(p for p in lr['primitives'] if p['kind'] != KIND_LINE)
        assert fb_circle['center'] == [500.0, 0.0]
        assert lr_circle['center'] == [0.0, 0.0]

    def test_symbol_position_is_relative_not_absolute(self) -> None:
        # パスが原点から遠くても、記号は第 1 頂点基準の小さな相対座標に置く
        # (絶対座標だと第 1 頂点ぶん二重にずれて本体から大きく離れる)。
        # 第1頂点(100,200,-50)・重心(100,700,-50) → 相対(0,500,0)
        # → front_back=(X,Z)=(0,0)、left_right=(Y,Z)=(500,0)。
        doc = build_document(
            _params(bar='D22', path=[[100.0, 200.0, -50.0], [100.0, 1200.0, -50.0]])
        )
        fb = next(m for m in doc['cut_marks'] if m['target'] == 'front_back')
        lr = next(m for m in doc['cut_marks'] if m['target'] == 'left_right')
        fb_circle = next(p for p in fb['primitives'] if p['kind'] != KIND_LINE)
        lr_circle = next(p for p in lr['primitives'] if p['kind'] != KIND_LINE)
        assert fb_circle['center'] == [0.0, 0.0]
        assert lr_circle['center'] == [500.0, 0.0]

    def test_axis_aligned_bar_end_on_symbol_on_axis(self) -> None:
        # 軸に沿った直線鉄筋の端面(left_right)記号は軸上(u=0)に来る:
        # X 軸に沿う鉄筋は Y が一定 → left_right の u=Y 相対=0。
        doc = build_document(
            _params(bar='D10', path=[[300.0, 400.0, 500.0], [1300.0, 400.0, 500.0]])
        )
        lr = next(m for m in doc['cut_marks'] if m['target'] == 'left_right')
        lr_dot = next(p for p in lr['primitives'] if p['kind'] != KIND_LINE)
        # 端面記号(●)は Y,Z が第1頂点と同じ → 相対 (0,0)
        assert lr_dot['center'] == [0.0, 0.0]

    def test_d13_symbol_is_cross(self) -> None:
        # D13 は × (線 2 本のみ)
        doc = build_document(_params(bar='D13'))
        primitives = doc['cut_marks'][0]['primitives']
        assert all(p['kind'] == KIND_LINE for p in primitives)
        assert len(primitives) == 2

    def test_mark_scale_affects_symbol_size(self) -> None:
        small = build_document(_params(bar='D22', mark_scale=2.0))
        large = build_document(_params(bar='D22', mark_scale=6.0))
        small_r = small['cut_marks'][0]['primitives'][0]['radius']
        large_r = large['cut_marks'][0]['primitives'][0]['radius']
        assert large_r == small_r * 3.0

    def test_empty_bar_raises(self) -> None:
        # 空文字は「未入力」としてユーザー向けメッセージを出す
        with pytest.raises(SpecError):
            build_document(_params(bar=''))

    def test_default_bar_when_missing(self) -> None:
        # キー欠落は既定 D13(最外径 14mm)
        params = _params()
        del params['bar']
        doc = build_document(params)
        assert doc['solid']['diameter'] == 14.0

    def test_default_mark_scale_when_missing(self) -> None:
        params = _params()
        del params['mark_scale']
        doc = build_document(params)  # 既定倍率で組み立つ
        assert doc['cut_marks']

    def test_non_positive_mark_scale_falls_back(self) -> None:
        doc = build_document(_params(mark_scale=-1.0))
        # 記号が正の半径で組み立つ(既定倍率へフォールバック)
        radii = [
            p['radius']
            for m in doc['cut_marks']
            for p in m['primitives']
            if p['kind'] != KIND_LINE
        ]
        assert all(r > 0 for r in radii)

    def test_duplicate_points_collapsed(self) -> None:
        doc = build_document(
            _params(path=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]])
        )
        # 連続重複は除かれ 2 頂点 → 1 セグメント
        assert len(doc['plan_lines']) == 1
        assert len(doc['solid']['path']) == 2

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
