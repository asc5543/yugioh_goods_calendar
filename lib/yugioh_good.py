"""
Utility for handing Yugioh Goods.
Author: asc5543
"""

class YugiohGoods:
  """The Yugioh goods with information."""

  def __init__(self, good_name: str, good_type: str, good_release_date: str, good_url: str = ""):
    self.good_name = good_name
    self.good_type = good_type
    self.good_release_date = good_release_date
    self.good_url = good_url
    self.good_description = ''
    self.good_short_name = None

  # TODO: Update format
  def __str__(self):
    return f'[{self.good_type}] {self.good_name} : {self.good_release_date}'

  def set_short_name(self, key: str, order: int):
    if order < 10:
      if len(key) == 2:
        self.good_short_name = key + '0' + str(order)
      elif len(key) == 3:
        self.good_short_name = key + str(order)
      else:
        print(f'Invalid key {key} and order {order}')
    else:
      if len(key) == 2:
        self.good_short_name = key + str(order)
      else:
        print(f'Invalid key {key} and order {order}')

  def set_good_description(self, description: str):
    self.good_description = description
