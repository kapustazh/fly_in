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
    "error_negative_drones.txt": "positive integer (got -1)",
    "error_nb_drones_zero.txt": "positive integer (got 0)",
    "error_nb_drones_not_first.txt": "first non-comment line must",
    "error_duplicate_nb_drones.txt": "nb_drones must appear only once",
    "error_invalid_zone_type.txt": "is not a valid ZoneTypes",
    "error_invalid_hub_metadata_key.txt": "Invalid 'speed'",
    "error_invalid_conn_metadata_key.txt": "Invalid 'speed'",
    "error_nonint_max_drones.txt": "'max_drones' must be an integer",
    "error_zero_max_drones.txt": "'max_drones' must be an integer",
    "error_nonint_link_capacity.txt": "'max_link_capacity' must be an integer",
    "error_self_connection.txt": "Self connection",
    "error_duplicate_connection.txt": "Duplicate connection",
    "error_missing_equals_in_metadata.txt": (
        "dictionary update sequence element"
    ),
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

    def test_parsing_errors_include_line_number(self) -> None:
        parser = InputParser()
        parser.parse_lines(str(MAPS_DIR / "error_negative_drones.txt"))
        with self.assertRaises(ParsingError) as cm:
            parser.parse_input()
        self.assertRegex(str(cm.exception), r"line 1:")

    def test_all_error_fixture_files_are_covered(self) -> None:
        fixture_names = {
            p.name for p in MAPS_DIR.glob("error_*.txt") if p.is_file()
        }
        self.assertEqual(fixture_names, set(EXPECTED_ERROR_SUBSTRINGS.keys()))

    def test_empty_file_requires_nb_drones(self) -> None:
        parser = InputParser()
        parser.parse_lines(str(MAPS_DIR / "empty.txt"))
        with self.assertRaises(ParsingError) as cm:
            parser.parse_input()
        self.assertIn("non-comment lines", str(cm.exception))

    def test_zone_name_with_dot_parses(self) -> None:
        """VII.4: zone names are not limited to [A-Za-z0-9_]."""
        text = (
            "nb_drones: 1\n"
            "start_hub: roof.v1 0 0\n"
            "end_hub: goal.area 1 0\n"
            "connection: roof.v1-goal.area\n"
        )
        parser = InputParser()
        parser.parsed_lines = text.splitlines(keepends=True)
        parser.parse_input()
        self.assertEqual(parser.number_of_drones, 1)
        self.assertIn("roof.v1", parser.get_zones)
        self.assertIn("goal.area", parser.get_zones)

    def test_connection_metadata_without_space_before_bracket(self) -> None:
        """connection: a-b[max_link=1] must not treat 'b[max_link=1]' as name."""
        text = (
            "nb_drones: 1\n"
            "start_hub: hub 0 0\n"
            "end_hub: goal 1 0\n"
            "connection: hub-goal[max_link_capacity=1]\n"
        )
        parser = InputParser()
        parser.parsed_lines = text.splitlines(keepends=True)
        parser.parse_input()
        self.assertIn("goal", parser.get_zones)
        self.assertIn("goal", parser.connections["hub"]["connections"])

    def test_known_valid_maps_parse(self) -> None:
        for filename in ("two_zones_valid.txt", "test_map.txt"):
            with self.subTest(filename=filename):
                parser = self._parse_file(filename)
                self.assertGreaterEqual(len(parser.get_zones), 2)


if __name__ == "__main__":
    unittest.main()
