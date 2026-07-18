"""鉄筋径の仕様パース (rebar.spec) のテスト。vs 非依存。"""
from __future__ import annotations

import pytest

from vectorworks_plugin_rebar_single.rebar.spec import (
    OUTER_DIAMETER,
    BarSize,
    SpecError,
    outer_diameter,
    parse_bar,
)


class TestParseBar:
    def test_d_prefix(self) -> None:
        assert parse_bar('D13') == BarSize(13, 14.0)

    def test_number_only(self) -> None:
        assert parse_bar('16') == BarSize(16, 18.0)

    def test_full_width_normalized(self) -> None:
        # 全角 Ｄ１９ → D19
        assert parse_bar('Ｄ１９') == BarSize(19, 21.0)

    def test_lowercase_d(self) -> None:
        assert parse_bar('d10') == BarSize(10, 11.0)

    def test_whitespace(self) -> None:
        assert parse_bar('  D25  ') == BarSize(25, 28.0)

    def test_empty_is_none(self) -> None:
        assert parse_bar('') is None
        assert parse_bar('   ') is None

    def test_invalid_raises(self) -> None:
        with pytest.raises(SpecError):
            parse_bar('D13@200')
        with pytest.raises(SpecError):
            parse_bar('abc')

    def test_zero_raises(self) -> None:
        with pytest.raises(SpecError):
            parse_bar('D0')


class TestOuterDiameter:
    def test_all_standard_sizes(self) -> None:
        # 標準図の最外径表の値を厳密に引く
        assert outer_diameter(10) == 11.0
        assert outer_diameter(41) == 46.0

    def test_table_matches_standard(self) -> None:
        # KSE 2008 の最外径表
        expected = {
            10: 11.0, 13: 14.0, 16: 18.0, 19: 21.0, 22: 25.0, 25: 28.0,
            29: 33.0, 32: 36.0, 35: 40.0, 38: 43.0, 41: 46.0,
        }
        assert OUTER_DIAMETER == expected

    def test_non_standard_approximated(self) -> None:
        # 表外の呼び径は最寄り標準径からスケール近似(正の値)
        value = outer_diameter(14)
        assert value > 0
        # 14 は 13 に最も近く、13→14 のスケールで概ね 14〜15 になる
        assert 13.0 < value < 16.0
