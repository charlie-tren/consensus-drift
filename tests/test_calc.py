"""The maths that decides what gets plotted and where.

The zero-sentinel tests are the important ones - they are the failure mode that
would silently wreck the chart rather than crash the build.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build import band, nice_bound                # noqa: E402
from fetch import gap_pp, revision_pct            # noqa: E402


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
