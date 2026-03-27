"""Unittests for parser fixtures under unit_tests/ or test_maps/.

Run:
    python3 -m unittest unit_tests.tests.test_parser_error_maps -v
"""

from __future__ import annotations

from pathlib import Path
import unittest

from parser import InputParser, ParsingError


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if (PROJECT_ROOT / "unit_tests").is_dir():
    MAPS_DIR = PROJECT_ROOT / "unit_tests"
else:
    MAPS_DIR = PROJECT_ROOT / "test_maps"


EXPECTED_ERROR_SUBSTRINGS: dict[str, str] = {
    "error_negative_drones.txt": "Number of drones can not be negative",
    "error_invalid_zone_type.txt": "is not a valid ZoneTypes",
    "error_invalid_hub_metadata_key.txt": "Invalid 'speed'",
    "error_invalid_conn_metadata_key.txt": "Invalid 'speed'",
    "error_nonint_max_drones.txt": "'max_drones' must be an integer",
    "error_zero_max_drones.txt": "'max_drones' must be an integer",
    "error_nonint_link_capacity.txt": "'max_link_capacity' must be an integer",
    "error_self_connection.txt": "Self connection",
    "error_duplicate_connection.txt": "Duplicate connection",
    "error_missing_equals_in_metadata.txt": "dictionary update sequence element",
}


class ParserErrorFixturesTests(unittest.TestCase):
    def _parse_file(self, filename: str) -> InputParser:
        parser = InputParser()
        parser.parse_lines(str(MAPS_DIR / filename))
        parser.parse_input()
        return parser

    def test_error_maps_raise_parsing_error(self) -> None:
        for filename, message_substring in EXPECTED_ERROR_SUBSTRINGS.items():
            with self.subTest(filename=filename):
                with self.assertRaises(ParsingError) as cm:
                    self._parse_file(filename)
                self.assertIn(message_substring, str(cm.exception))

    def test_all_error_fixture_files_are_covered(self) -> None:
        fixture_names = {
            p.name for p in MAPS_DIR.glob("error_*.txt") if p.is_file()
        }
        self.assertEqual(fixture_names, set(EXPECTED_ERROR_SUBSTRINGS.keys()))

    def test_empty_file_is_allowed(self) -> None:
        parser = self._parse_file("empty.txt")
        self.assertEqual(parser.number_of_drones, 0)
        self.assertEqual(parser.get_zones, {})
        self.assertEqual(parser.connections, {})

    def test_known_valid_maps_parse(self) -> None:
        for filename in ("two_zones_valid.txt", "test_map.txt"):
            with self.subTest(filename=filename):
                parser = self._parse_file(filename)
                self.assertGreaterEqual(len(parser.get_zones), 2)


if __name__ == "__main__":
    unittest.main()
