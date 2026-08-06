"""The maths that decides what gets plotted and where.

The zero-sentinel tests are the important ones - they are the failure mode that
would silently wreck the chart rather than crash the build.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from build import nice_bound                      # noqa: E402
from fetch import quadrant, revision_pct          # noqa: E402


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

    def test_none_either_side(self):
        assert revision_pct(None, 1.0) is None
        assert revision_pct(1.0, None) is None


class TestQuadrant:
    def test_both_up_is_earned(self):
        assert quadrant(5.0, 5.0) == "earned"

    def test_price_up_estimates_down_is_unearned(self):
        assert quadrant(5.0, -5.0) == "unearned"

    def test_estimates_up_price_down_is_overlooked(self):
        assert quadrant(-5.0, 5.0) == "overlooked"

    def test_both_down_is_confirmed(self):
        assert quadrant(-5.0, -5.0) == "confirmed"

    def test_exact_zero_counts_as_up(self):
        # a name sitting exactly on an axis has to land somewhere deterministic
        assert quadrant(0.0, 0.0) == "earned"

    def test_missing_inputs_give_no_quadrant(self):
        assert quadrant(None, 1.0) is None


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
