import os
import sys
import unittest
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from app.security import enum_value, positive_id, required_text  # noqa: E402


class ValidationTests(unittest.TestCase):
    def test_required_text_trims_whitespace(self):
        self.assertEqual(required_text({"name": "  A Farmer "}, "name"), "A Farmer")

    def test_required_text_rejects_empty_value(self):
        with self.assertRaisesRegex(ValueError, "is required"):
            required_text({"name": "  "}, "name")

    def test_required_text_enforces_maximum(self):
        with self.assertRaisesRegex(ValueError, "characters or fewer"):
            required_text({"name": "abcd"}, "name", maximum=3)

    def test_positive_id_rejects_non_positive_values(self):
        for value in ("bad", 0, -3, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                positive_id(value)

    def test_enum_value_uses_only_allowed_values(self):
        self.assertEqual(enum_value({"role": "farmer"}, "role", ("farmer", "trainer")), "farmer")
        with self.assertRaisesRegex(ValueError, "one of"):
            enum_value({"role": "root"}, "role", ("farmer", "trainer"))


if __name__ == "__main__":
    unittest.main()
