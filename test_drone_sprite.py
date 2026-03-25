"""Tests for drone atlas bank selection (no pygame display required)."""

import unittest

from drone_sprite import bank_key_for_velocity, screen_heading_deg


class BankKeyForVelocityTests(unittest.TestCase):
    def test_screen_heading_y_down_matches_rotate_convention(self) -> None:
        self.assertAlmostEqual(screen_heading_deg(1.0, 0.0), 0.0)
        self.assertAlmostEqual(screen_heading_deg(0.0, 1.0), -90.0)

    def test_se_diagonal_uses_right_down_row(self) -> None:
        # Magnitude must exceed default dead_zone (1.5); hypot(1,1) < 1.5.
        self.assertEqual(bank_key_for_velocity(10.0, 10.0), "right_down")

    def test_sw_diagonal_uses_merged_left_down(self) -> None:
        self.assertEqual(bank_key_for_velocity(-10.0, 10.0), "left_down")

    def test_idle_inside_dead_zone(self) -> None:
        self.assertEqual(bank_key_for_velocity(0.0, 0.0), "idle")

    def test_pure_east_closer_to_right_down(self) -> None:
        self.assertEqual(bank_key_for_velocity(50.0, 0.0), "right_down")

    def test_pure_west_closer_to_left_down(self) -> None:
        self.assertEqual(bank_key_for_velocity(-50.0, 0.0), "left_down")

    def test_equidistant_uses_dx_sign(self) -> None:
        # Straight down: heading -90°, equidistant from natives -45° and -135°.
        self.assertEqual(bank_key_for_velocity(0.0, 10.0), "right_down")
        self.assertEqual(bank_key_for_velocity(-0.01, 10.0), "left_down")


if __name__ == "__main__":
    unittest.main()
