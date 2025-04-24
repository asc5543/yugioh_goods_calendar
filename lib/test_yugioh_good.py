from unittest import TestCase

from lib import yugioh_good


class TestYugiohGoods(TestCase):
    def setUp(self):
        self.good = yugioh_good.YugiohGoods(
            "test",
            "test",
            "test"
        )

    def test_set_short_name_number_small_than_ten(self):
        self.good.set_short_name("11", 9)
        self.assertEqual(
            self.good.good_short_name,
            "1109",
        )

    def test_set_1301_special_case(self):
        self.good.set_short_name("12", 9)
        self.assertEqual(
            self.good.good_short_name,
            "1301",
        )

    def test_set_short_name_number_big_than_ten(self):
        self.good.set_short_name("11", 10)
        self.assertEqual(
            self.good.good_short_name,
            "1110",
        )

    def test_set_short_name_wpp(self):
        self.good.set_short_name("WPP", 1)
        self.assertEqual(
            self.good.good_short_name,
            "WPP1",
        )