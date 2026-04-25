"""
Utility for handing Yugioh Goods.
Author: asc5543
"""
from typing import Optional


class YugiohGoods:
    """Object representation of Yugioh product information."""

    def __init__(
        self,
        good_name: str,
        good_type: str,
        good_release_date: str,
        good_url: str = "",
        card_list_url: str = ""
    ):
        self.good_name = good_name
        self.good_type = good_type
        self.good_release_date = good_release_date
        self.good_url = good_url
        self.good_description: str = ''
        self.good_short_name: Optional[str] = None
        self.card_list_url = card_list_url

    def __str__(self) -> str:
        return (f'[{self.good_type}] {self.good_name} : '
                f'{self.good_release_date}')

    def set_short_name(self, key: str, order: int):
        """
        Generates short names (e.g., 1201, AC01).
        Includes logic for transition from Series 12 to 13.
        """
        # Series 12 basic packs transition to Series 13 after the 8th pack
        if key == '12' and order > 8:
            key = '13'
            order -= 8

        # Formatting with zero-padding
        if order < 10:
            if len(key) == 2:
                self.good_short_name = f"{key}0{order}"
            elif len(key) == 3:
                self.good_short_name = f"{key}{order}"
            else:
                print(f'Invalid key {key} or order {order}')
        else:
            self.good_short_name = f"{key}{order}"

    def set_good_description(self, description: str):
        self.good_description = description

    def set_card_list_url(self, url: str):
        self.card_list_url = url
