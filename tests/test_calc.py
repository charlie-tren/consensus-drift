"""The maths that decides what gets plotted and where.

The zero-sentinel tests are the important ones - they are the failure mode that
would silently wreck the chart rather than crash the build.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build import MCAP_BANDS, band, country_of, mcap_band, nice_bound   # noqa: E402
from fetch import (MAX_RATE_LIMIT_SHARE, gap_pp, is_rate_limit, path_break,   # noqa: E402
                   revision_pct)


class TestRevisionPct:
    def test_plain_upgrade(self):
        assert revision_pct(11.0, 10.0) == 10.0

    def test_plain_downgrade(self):
        assert revision_pct(9.0, 10.0) == -10.0

    def test_loss_maker_narrowing_is_an_upgrade(self):
        # -1.00 -> -0.50 is analysts getting LESS pessimistic; dividing by the raw
        # (negative) base would flip the sign and call it a downgrade
        assert revision_pct(-0.5, -1.0) == 50.0

    def test_loss_maker_widening_is_a_downgrade(self):
        assert revision_pct(-1.5, -1.0) == -50.0

    # --- the Yahoo zero sentinel: a missing prior estimate comes back as 0.0 ---
    def test_zero_prior_is_missing_not_infinite(self):
        assert revision_pct(6.72, 0.0) is None      # observed on CBA.AX

    def test_zero_current_is_missing(self):
        assert revision_pct(0.0, 6.72) is None

    # a base near zero makes the percentage meaningless - WBD came back with a prior
    # estimate of -0.001 and a "revision" of +7116%, which alone set the chart axis
    def test_near_zero_base_is_rejected(self):
        assert revision_pct(0.039, -0.001) is None

    def test_small_but_usable_base_is_kept(self):
        assert revision_pct(0.15, 0.12) is not None

    def test_floor_is_on_the_prior_not_the_current(self):
        assert revision_pct(0.001, 5.0) is not None

    # a sign flip is not a comparable percentage - ECHO went -0.114 -> +15.64 and
    # reported +13,816%, sorting to the top of the page
    def test_loss_turning_into_profit_is_rejected(self):
        assert revision_pct(15.6367, -0.1140) is None

    def test_profit_turning_into_loss_is_rejected(self):
        assert revision_pct(-0.153, 0.134) is None

    def test_same_sign_large_move_is_kept(self):
        assert revision_pct(15.0, 1.0) is not None

    def test_none_either_side(self):
        assert revision_pct(None, 1.0) is None
        assert revision_pct(1.0, None) is None


class TestGap:
    def test_gap_is_estimates_minus_price(self):
        assert round(gap_pp(3.77, 14.80), 2) == 11.03

    def test_gap_negative_when_price_outruns(self):
        assert round(gap_pp(43.37, 1.38), 2) == -41.99

    def test_missing_either_side(self):
        assert gap_pp(None, 1.0) is None
        assert gap_pp(1.0, None) is None


class TestBand:
    # the NVDA case: sign-of-each-axis called this "both up" and filed it with names
    # whose price had run 40% on a 1% upgrade. It is the opposite situation.
    def test_nvda_reads_as_price_behind(self):
        assert band(14.80 - 3.77) == "behind"

    def test_price_running_ahead_of_a_small_upgrade(self):
        assert band(1.38 - 43.37) == "ahead"

    def test_both_down_together_is_in_line(self):
        assert band(-3.0 - -4.0) == "inline"

    def test_both_up_together_is_in_line(self):
        assert band(9.0 - 8.0) == "inline"

    def test_threshold_is_inclusive(self):
        assert band(10.0) == "behind"
        assert band(-10.0) == "ahead"
        assert band(9.9) == "inline"

    def test_missing_gap_is_in_line(self):
        assert band(None) == "inline"


class TestNiceBound:
    def test_pads_beyond_the_extreme(self):
        # the largest point must never sit exactly on the frame
        assert nice_bound([43.2]) > 43.2

    def test_symmetric_on_sign(self):
        assert nice_bound([-43.2]) == nice_bound([43.2])

    def test_floor_applies_to_a_flat_universe(self):
        assert nice_bound([0.1, -0.2]) == 5.0

    def test_empty_universe_does_not_crash(self):
        assert nice_bound([]) == 5.0

    def test_large_values_still_bounded(self):
        assert nice_bound([180.0]) >= 180.0


class TestCountryOf:
    """The table cell shows the country; the full label rides in a title attribute
    and is what the column filter matches, so both halves have to survive."""

    def test_splits_on_the_bracket(self):
        assert country_of("Australia (ASX)") == "Australia"

    def test_keeps_multi_word_countries(self):
        assert country_of("United States (NYSE & Nasdaq)") == "United States"
        assert country_of("New Zealand (NZX)") == "New Zealand"

    def test_bracketed_exchange_can_itself_contain_spaces(self):
        assert country_of("Netherlands (Euronext Amsterdam)") == "Netherlands"

    def test_label_without_a_bracket_passes_through(self):
        assert country_of("Australia") == "Australia"


class TestPathBreak:
    """Real paths off Yahoo, 07/08/2026. The three that must drop were all in the
    top ten moves on the page; the four that must survive are real downgrades of a
    comparable size, which is what makes this worth testing rather than eyeballing."""

    def test_mid_path_step_is_a_break(self):
        # HON: calm, then -59% in one month, then calm again
        assert path_break([23.00184, 22.96087, 9.38141, 9.77527, 10.01358]) is not None

    def test_outlying_base_is_a_break(self):
        # IFT.NZ: the 90-day base alone is out of line, and it was the top row
        assert path_break([0.13, 0.42014, 0.27869, 0.32536, 0.32536]) is not None

    def test_step_at_the_base_is_a_break(self):
        # FLEX: +69% between 90d and 60d, flat for the remaining two months
        assert path_break([4.1137, 6.95217, 6.95217, 6.92411, 7.11111]) is not None

    def test_progressive_downgrade_survives(self):
        # 360.AX, a genuine -55.6% ground out over the whole quarter
        assert path_break([2.11406, 1.53161, 1.26403, 0.93508, 0.93832]) is None

    def test_choppy_but_progressive_survives(self):
        assert path_break([0.30494, 0.19144, 0.18444, 0.20788, 0.12354]) is None
        assert path_break([2.79864, 2.42024, 2.42024, 2.08048, 1.26279]) is None

    def test_loss_maker_survives(self):
        # all negative: the ratios still work, a widening loss is not a break
        assert path_break([-0.11547, -0.16365, -0.16365, -0.1865, -0.1865]) is None

    def test_too_few_points_is_not_evidence_of_a_break(self):
        assert path_break([None, None, None, 1.0, 2.0]) is None
        assert path_break([]) is None

    def test_zeros_are_dropped_not_treated_as_estimates(self):
        # Yahoo's missing sentinel is 0.0; it must not create an infinite step
        assert path_break([0.0, 0.0, 1.0, 1.02, 1.05]) is None

    def test_sign_flip_left_to_the_existing_guard(self):
        assert path_break([-0.114, 0.5, 4.0, 12.0, 15.64]) is None


class TestMcapBands:
    """The dropdown is ordered from MCAP_BANDS and the rows are labelled by
    mcap_band. When those were two separate copies of the same strings, relabelling
    one emptied the size filter on the live page with a green build and green tests."""

    def test_every_label_mcap_band_can_return_is_in_the_ordering(self):
        produced = {mcap_band(v) for v in (None, 0.5, 49.9, 50, 249.9, 250, 9_999)}
        assert produced <= set(MCAP_BANDS)

    def test_ordering_contains_nothing_unreachable(self):
        reachable = {mcap_band(v) for v in (None, 1, 100, 1_000)}
        assert set(MCAP_BANDS) == reachable

    def test_boundaries_are_inclusive_upward(self):
        assert mcap_band(49.99) == "Under US$50bn"
        assert mcap_band(50) == "US$50bn to US$250bn"
        assert mcap_band(249.99) == "US$50bn to US$250bn"
        assert mcap_band(250) == "Over US$250bn"


class TestRateLimitDetection:
    """The publish guard is only as good as this predicate. If it stops recognising a
    rate limit, the run stops refusing to publish and goes back to shipping a third of
    the universe silently - the 09/08/2026 failure, which nothing caught for two days.

    Matched on class name and message rather than an imported symbol on purpose:
    `YFRateLimitError` has moved module between yfinance versions, and an ImportError
    would disable the guard without failing anything.
    """

    def test_catches_the_real_yfinance_exception(self):
        from yfinance.exceptions import YFRateLimitError
        assert is_rate_limit(YFRateLimitError())

    def test_catches_it_by_class_name_alone(self):
        class YFRateLimitError(Exception):      # a renamed / relocated future version
            pass
        assert is_rate_limit(YFRateLimitError("anything"))

    def test_catches_it_by_message_alone(self):
        assert is_rate_limit(RuntimeError("Too Many Requests. Rate limited."))

    def test_a_real_data_gap_is_not_a_rate_limit(self):
        # This is the half that matters: a genuine gap must NOT be retried or counted
        # against the ceiling, or a legitimately thin universe blocks publication.
        assert not is_rate_limit(KeyError("+1y"))
        assert not is_rate_limit(ValueError("no eps_trend from Yahoo"))

    def test_the_ceiling_is_a_share_not_a_count(self):
        # 5% of ~1,300 names is ~65. The 09/08 run had 750 still missing, which must
        # be nowhere near passing.
        assert 750 / 1309 > MAX_RATE_LIMIT_SHARE
        assert 40 / 1309 < MAX_RATE_LIMIT_SHARE
