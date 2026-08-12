import unittest

from proofnav.offline.m3b_terminal_experiment import (
    minimum_zero_error_units,
    one_sided_clopper_pearson_upper,
)


class M3BStatisticalSemanticsTests(unittest.TestCase):

    def test_exact_one_sided_scan_familywise_bounds(self):
        self.assertAlmostEqual(
            one_sided_clopper_pearson_upper(2, 6),
            0.7286616274802475,
            places=12,
        )
        self.assertAlmostEqual(
            one_sided_clopper_pearson_upper(0, 6),
            0.39303776899708276,
            places=12,
        )
        self.assertEqual(minimum_zero_error_units(), 59)

    def test_invalid_pseudoreplicated_or_empty_units_fail(self):
        for errors, units in ((0, 0), (2, 1), (-1, 6)):
            with self.subTest(errors=errors, units=units):
                with self.assertRaises(ValueError):
                    one_sided_clopper_pearson_upper(errors, units)


if __name__ == "__main__":
    unittest.main()
