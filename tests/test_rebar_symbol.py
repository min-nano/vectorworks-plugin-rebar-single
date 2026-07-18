"""断面表示記号のプロファイル組み立て (rebar.symbol) のテスト。vs 非依存。"""
from __future__ import annotations

from typing import List

from vectorworks_plugin_rebar_single.document import (
    KIND_DISK,
    KIND_POLYGON,
    KIND_RING,
    Profile,
)
from vectorworks_plugin_rebar_single.rebar.symbol import build_symbol_profiles


def _kinds(profiles: List[Profile]) -> List[str]:
    return [p['kind'] for p in profiles]


class TestBuildSymbolProfiles:
    def test_d10_filled_disk(self) -> None:
        # ● 塗り丸: disk 1 個
        profiles = build_symbol_profiles(10, 40.0)
        assert _kinds(profiles) == [KIND_DISK]
        assert profiles[0]['radius'] == 20.0  # r = size/2

    def test_d19_filled_disk(self) -> None:
        assert _kinds(build_symbol_profiles(19, 40.0)) == [KIND_DISK]

    def test_d13_cross_two_strips(self) -> None:
        # × 斜め十字: polygon(帯)2 本・円なし
        profiles = build_symbol_profiles(13, 40.0)
        assert _kinds(profiles) == [KIND_POLYGON, KIND_POLYGON]

    def test_d16_ring_and_slash(self) -> None:
        # ⊘ リング + 斜線
        assert _kinds(build_symbol_profiles(16, 40.0)) == [KIND_RING, KIND_POLYGON]

    def test_d22_ring(self) -> None:
        # ○ リング(中空)
        profiles = build_symbol_profiles(22, 40.0)
        assert _kinds(profiles) == [KIND_RING]
        ring = profiles[0]
        assert ring['outer'] == 20.0
        assert 0 < ring['inner'] < ring['outer']

    def test_d25_ring_and_center_dot(self) -> None:
        # ⊙ リング + 中心の塗り丸
        assert _kinds(build_symbol_profiles(25, 40.0)) == [KIND_RING, KIND_DISK]

    def test_d29_ring_and_cross(self) -> None:
        # ⊗ リング + × 帯 2 本
        assert _kinds(build_symbol_profiles(29, 40.0)) == [
            KIND_RING, KIND_POLYGON, KIND_POLYGON
        ]

    def test_d32_double_ring(self) -> None:
        # ◎ 二重リング
        profiles = build_symbol_profiles(32, 40.0)
        assert _kinds(profiles) == [KIND_RING, KIND_RING]
        assert profiles[1]['outer'] < profiles[0]['outer']

    def test_d35_ring_and_plus(self) -> None:
        # ⊕ リング + 十字 帯 2 本
        assert _kinds(build_symbol_profiles(35, 40.0)) == [
            KIND_RING, KIND_POLYGON, KIND_POLYGON
        ]

    def test_d38_dot_and_plus(self) -> None:
        # ●⊕ 塗り丸 + 十字 帯 2 本
        assert _kinds(build_symbol_profiles(38, 40.0)) == [
            KIND_DISK, KIND_POLYGON, KIND_POLYGON
        ]

    def test_d41_ring_and_cross(self) -> None:
        assert _kinds(build_symbol_profiles(41, 40.0)) == [
            KIND_RING, KIND_POLYGON, KIND_POLYGON
        ]

    def test_size_scales_radius(self) -> None:
        small = build_symbol_profiles(22, 40.0)[0]
        large = build_symbol_profiles(22, 80.0)[0]
        assert small['outer'] == 20.0
        assert large['outer'] == 40.0

    def test_polygon_has_four_corners(self) -> None:
        # 帯(strip)は 4 頂点の長方形
        strip = next(
            p for p in build_symbol_profiles(13, 40.0) if p['kind'] == KIND_POLYGON
        )
        assert len(strip['points']) == 4

    def test_non_standard_uses_nearest(self) -> None:
        assert build_symbol_profiles(14, 40.0)  # 空でない

    def test_disks_and_rings_centered_at_origin(self) -> None:
        for nominal in (10, 13, 16, 19, 22, 25, 29, 32, 35, 38, 41):
            for p in build_symbol_profiles(nominal, 40.0):
                if p['kind'] in (KIND_DISK, KIND_RING):
                    assert p['center'] == [0.0, 0.0]
