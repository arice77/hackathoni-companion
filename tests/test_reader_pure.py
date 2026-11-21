import unittest

from companion.reader import is_placeholder_choice


class PlaceholderTests(unittest.TestCase):
    def test_placeholders(self):
        for v in ["Select", "---Select Classification---", "---Select My Service---", "", "  ", "Choose...", "--select--"]:
            self.assertTrue(is_placeholder_choice(v), v)

    def test_real_choices(self):
        for v in ["Flood", "Insurance & Calamity Relief Services", "Crop Insurance Compensation", "12-08-2026 (TEST FIR)"]:
            self.assertFalse(is_placeholder_choice(v), v)


if __name__ == "__main__":
    unittest.main()
