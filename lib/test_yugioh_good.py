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
        self.good.set_short_name("12", 9)
        self.assertEqual(
            self.good.good_short_name,
            "1209",
        )

    def test_set_short_name_number_big_than_ten(self):
        self.good.set_short_name("12", 10)
        self.assertEqual(
            self.good.good_short_name,
            "1210",
        )

    def test_set_short_name_wpp(self):
        self.good.set_short_name("WPP", 1)
        self.assertEqual(
            self.good.good_short_name,
            "WPP1",
        )