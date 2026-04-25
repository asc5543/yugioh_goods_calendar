from unittest import TestCase
from lib import yugioh_good


class TestYugiohGoods(TestCase):
    def setUp(self):
        # Initializing with dummy data for basic setup
        self.good = yugioh_good.YugiohGoods(
            "RAGE OF THE ABYSS",
            "基本パック",
            "2024年7月27日"
        )

    # --- Existing Tests (Standardized to 4-space indent) ---

    def test_set_short_name_number_smaller_than_ten(self):
        self.good.set_short_name("11", 9)
        self.assertEqual(self.good.good_short_name, "1109")

    def test_set_1301_special_case(self):
        """Tests the transition boundary where 1209 becomes 1301."""
        self.good.set_short_name("12", 9)
        self.assertEqual(self.good.good_short_name, "1301")

    def test_set_short_name_number_bigger_than_ten(self):
        self.good.set_short_name("11", 10)
        self.assertEqual(self.good.good_short_name, "1110")

    def test_set_short_name_wpp(self):
        self.good.set_short_name("WPP", 1)
        self.assertEqual(self.good.good_short_name, "WPP1")

    # --- New Recommended Tests ---

    def test_set_1208_edge_case(self):
        """Tests the last pack of Series 12
        before the transition logic kicks in."""
        self.good.set_short_name("12", 8)
        self.assertEqual(self.good.good_short_name, "1208")

    def test_set_1302_after_transition(self):
        """Tests if the offset works correctly for packs
        beyond the first transition pack."""
        # 1210 should become 1302 (10 - 8 = 2)
        self.good.set_short_name("12", 10)
        self.assertEqual(self.good.good_short_name, "1302")

    def test_set_short_name_3_char_key_double_digit(self):
        """Tests 3-character keys (like PAC or AC) with double-digit order."""
        self.good.set_short_name("PAC", 10)
        self.assertEqual(self.good.good_short_name, "PAC10")

    def test_set_short_name_invalid_key_length(self):
        """Tests behavior when an unexpected key length is provided
        (e.g., '1')."""
        # Based on current logic, this prints an error
        self.good.set_short_name("1", 5)
        self.assertIsNone(self.good.good_short_name)

    def test_set_good_description(self):
        """Tests if description is correctly updated."""
        desc = "Type: Booster Pack\nURL: http://test.com"
        self.good.set_good_description(desc)
        self.assertEqual(self.good.good_description, desc)

    def test_set_card_list_url(self):
        """Tests if the card list URL is correctly updated."""
        url = "https://ntucgm.blogspot.com/test"
        self.good.set_card_list_url(url)
        self.assertEqual(self.good.card_list_url, url)

    def test_str_representation(self):
        """Tests the __str__ method for logging/debugging purposes."""
        expected_str = "[基本パック] RAGE OF THE ABYSS : 2024年7月27日"
        self.assertEqual(str(self.good), expected_str)

    def test_initial_values(self):
        """Smoke test for the constructor's default values."""
        new_good = yugioh_good.YugiohGoods("Name", "Type", "Date")
        self.assertEqual(new_good.good_url, "")
        self.assertEqual(new_good.card_list_url, "")
        self.assertIsNone(new_good.good_short_name)
