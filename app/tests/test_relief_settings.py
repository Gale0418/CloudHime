import unittest

from settings_store import normalize_settings_payload, resolve_relief_offsets


class ReliefSettingsTests(unittest.TestCase):
    def test_legacy_direction_and_gap_are_dropped_and_default_to_zero(self):
        normalized = normalize_settings_payload(
            {"region_relief_side": "right", "region_relief_gap_px": 80},
            40,
        )

        self.assertEqual(
            (normalized["region_relief_offset_x"], normalized["region_relief_offset_y"]),
            (0, 0),
        )
        self.assertNotIn("region_relief_side", normalized)
        self.assertNotIn("region_relief_gap_px", normalized)

    def test_offsets_are_clamped_to_supported_range(self):
        self.assertEqual(
            resolve_relief_offsets(
                {"region_relief_offset_x": -1900, "region_relief_offset_y": 1900}
            ),
            (-1000, 1000),
        )

    def test_expanded_offsets_survive_settings_normalization(self):
        normalized = normalize_settings_payload(
            {"region_relief_offset_x": -875, "region_relief_offset_y": 935}, 40
        )
        self.assertEqual(resolve_relief_offsets(normalized), (-875, 935))


if __name__ == "__main__":
    unittest.main()
