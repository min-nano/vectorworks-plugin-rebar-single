"""断面表示記号の組み立て (rebar.symbol) のテスト。vs 非依存。"""
from __future__ import annotations

from typing import List

from vectorworks_plugin_rebar_single.document import KIND_CIRCLE, KIND_LINE, Primitive
from vectorworks_plugin_rebar_single.rebar.symbol import build_symbol, translate


def _circles(primitives: List[Primitive]) -> List[Primitive]:
    return [p for p in primitives if p['kind'] == KIND_CIRCLE]


def _lines(primitives: List[Primitive]) -> List[Primitive]:
    return [p for p in primitives if p['kind'] == KIND_LINE]


class TestBuildSymbol:
    def test_d10_filled_dot(self) -> None:
        # ● 塗り丸: 円 1 個・塗りあり・線なし
        primitives = build_symbol(10, 40.0)
        circles = _circles(primitives)
        assert len(circles) == 1
        assert circles[0]['filled'] is True
        assert not _lines(primitives)

    def test_d19_filled_dot(self) -> None:
        primitives = build_symbol(19, 40.0)
        circles = _circles(primitives)
        assert len(circles) == 1 and circles[0]['filled'] is True

    def test_d13_cross(self) -> None:
        # × 斜め十字: 線 2 本・円なし
        primitives = build_symbol(13, 40.0)
        assert len(_lines(primitives)) == 2
        assert not _circles(primitives)

    def test_d16_circle_slash(self) -> None:
        # ⊘ 丸 + 斜線 1 本
        primitives = build_symbol(16, 40.0)
        assert len(_circles(primitives)) == 1
        assert len(_lines(primitives)) == 1

    def test_d22_open_circle(self) -> None:
        # ○ 丸: 円 1 個・塗りなし・線なし
        primitives = build_symbol(22, 40.0)
        circles = _circles(primitives)
        assert len(circles) == 1 and circles[0]['filled'] is False
        assert not _lines(primitives)

    def test_d25_circle_with_center_dot(self) -> None:
        # ⊙ 丸 + 中心の点: 円 2 個(外=塗りなし・中心=塗りあり)
        primitives = build_symbol(25, 40.0)
        circles = _circles(primitives)
        assert len(circles) == 2
        filled = [c for c in circles if c['filled']]
        assert len(filled) == 1  # 中心の点だけ塗り

    def test_d29_circle_cross(self) -> None:
        # ⊗ 丸 + 内側の ×: 円 1 個 + 線 2 本
        primitives = build_symbol(29, 40.0)
        assert len(_circles(primitives)) == 1
        assert len(_lines(primitives)) == 2

    def test_d32_double_circle(self) -> None:
        # ◎ 二重丸: 円 2 個(両方塗りなし)・線なし
        primitives = build_symbol(32, 40.0)
        circles = _circles(primitives)
        assert len(circles) == 2
        assert all(c['filled'] is False for c in circles)
        assert not _lines(primitives)

    def test_d35_circle_plus(self) -> None:
        # ⊕ 丸 + 十字線: 円 1 個 + 線 2 本(縦横)
        primitives = build_symbol(35, 40.0)
        assert len(_circles(primitives)) == 1
        assert len(_lines(primitives)) == 2

    def test_d38_dot_plus(self) -> None:
        # ●⊕ 塗り丸 + 十字線: 塗り円 1 個 + 線 2 本
        primitives = build_symbol(38, 40.0)
        circles = _circles(primitives)
        assert len(circles) == 1 and circles[0]['filled'] is True
        assert len(_lines(primitives)) == 2

    def test_d41_circle_cross(self) -> None:
        primitives = build_symbol(41, 40.0)
        assert len(_circles(primitives)) == 1
        assert len(_lines(primitives)) == 2

    def test_size_scales_radius(self) -> None:
        # 外径 size の円の半径は size/2
        small = _circles(build_symbol(22, 40.0))[0]
        large = _circles(build_symbol(22, 80.0))[0]
        assert small['radius'] == 20.0
        assert large['radius'] == 40.0

    def test_non_standard_uses_nearest_shape(self) -> None:
        # 表外の呼び径でも記号が組み立てられる(最寄り標準径の形)
        primitives = build_symbol(14, 40.0)
        assert primitives  # 空でない

    def test_all_primitives_centered_at_origin(self) -> None:
        # 記号は中心 (0,0) 基準に組み立てる(配置は translate で与える)
        for nominal in (10, 13, 16, 19, 22, 25, 29, 32, 35, 38, 41):
            for p in build_symbol(nominal, 40.0):
                if p['kind'] == KIND_CIRCLE:
                    assert p['center'] == [0.0, 0.0]


class TestTranslate:
    def test_circle_center_moves(self) -> None:
        moved = translate(build_symbol(22, 40.0), 100.0, -50.0)
        circle = next(p for p in moved if p['kind'] == KIND_CIRCLE)
        assert circle['center'] == [100.0, -50.0]
        assert circle['radius'] == 20.0  # 半径は不変

    def test_line_endpoints_move(self) -> None:
        moved = translate(build_symbol(13, 40.0), 10.0, 20.0)
        line = next(p for p in moved if p['kind'] == KIND_LINE)
        # D13 の × は (-20,-20)-(20,20) 等。平行移動で両端が動く
        assert line['start'] == [-20.0 + 10.0, -20.0 + 20.0]
        assert line['end'] == [20.0 + 10.0, 20.0 + 20.0]

    def test_zero_translation_is_identity(self) -> None:
        base = build_symbol(29, 40.0)
        assert translate(base, 0.0, 0.0) == base

    def test_does_not_mutate_input(self) -> None:
        base = build_symbol(22, 40.0)
        before = [dict(p) for p in base]
        translate(base, 5.0, 5.0)
        assert base == before
