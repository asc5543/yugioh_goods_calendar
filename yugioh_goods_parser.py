import time

from bs4 import BeautifulSoup
from config import config
from lib import google_calendar_handler
from lib import yugioh_good

import datetime
import json, tempfile
import os
import re

from urllib.parse import quote
from urllib.request import urlopen

# Goods Pattern
# p[174]={"id":"cg1641","status":"","class-name":"構築済みデッキ","class-key":"structure","type":"ストラクチャーR",
#         "title":"STRUCTURE DECK R - ウォリアーズ・ストライク -","thumbnail":"thumbnail/cg1641.png",
#         "price-intax":"1,100円","price-extax":" (本体価格 1,000円）","release-date":"2019年9月28日(土)",
#         "soon":"none","limited":'none',"url":"sr09","detail":"page"};
# if url exists, config.YGO_GOOD_INFO_URL  + "/" + url = link of the good
_goods_pattern = re.compile('p\\[\\d+].+;')
_type_pattern = re.compile(',\"type\":\"([^"]*)\"')
_title_pattern = re.compile(',\"title\":\"([^"]*)\"')
_release_date_pattern = re.compile(',\"release-date\":\"([^"]*)\"')
_url_pattern = re.compile(',\"url\":\"([^"]*)\"')

# Need a method to know the good order in the same type
# Ex. RAGE OF THE ABYSS is 1206, ANIMATION CHRONICLE 2024 is AC04
_pack_list_per_type = {}
_no_list_type = ['プロテクター']

# Get card list url from ntucgm
def find_card_list(goods_name: str) -> str:
  time.sleep(2) # Avoid anti-crawler
  ntucgm_url = r"https://ntucgm.blogspot.com/search?q=" + quote(goods_name)
  search_page = urlopen(ntucgm_url)
  content = search_page.read().decode('utf-8')
  soup = BeautifulSoup(content, 'html.parser')
  script_tag = soup.find('script', type='application/ld+json')
  if not script_tag:
    print('No card list exist!!')
    return ""
  script_content = script_tag.string.strip()
  match = re.search(r'"@id":\s*"([^"]+)"', script_content)

  if match:
    url = match.group(1)
    return url
  else:
    print('No match found')
    return ""

def goods_parse(goods_matches: list[str]) -> list[yugioh_good.YugiohGoods]:
  """Generate Goods information from raw list."""
  goods_list = []
  for good_str in goods_matches:
    good = good_parse(good_str)
    if good.good_type in config.TYPE_SHORTNAME_DICT:
      key = config.TYPE_SHORTNAME_DICT[good.good_type]
      # Organize the good type.
      if not key in _pack_list_per_type:
        _pack_list_per_type[key] = []
      _pack_list_per_type[key].append(good.good_name)
    elif "ANIMATION CHRONICLE" in good.good_name:
      if not 'AC' in _pack_list_per_type:
        _pack_list_per_type['AC'] = []
      _pack_list_per_type['AC'].append(good.good_name)
    goods_list.append(good)

  # Reverse the order to ascend oder
  for key in _pack_list_per_type:
    _pack_list_per_type[key].reverse()

  return goods_list


def good_parse(good_str: str) -> yugioh_good.YugiohGoods|None:
  """Generate Good information from raw string."""

  type_match = _type_pattern.search(good_str)
  title_match = _title_pattern.search(good_str)
  release_date_match = _release_date_pattern.search(good_str)
  url_match = _url_pattern.search(good_str)

  if type_match and title_match and release_date_match:
    return yugioh_good.YugiohGoods(
      good_name=title_match.group(1),
      good_type=type_match.group(1),
      good_release_date=release_date_match.group(1),
      good_url=url_match.group(1)
    )
  else:
    return None


def get_good_title(good: yugioh_good.YugiohGoods) -> str:
  if good.good_short_name:
    return f'[{good.good_short_name}] {good.good_name}'
  return good.good_name


def convert_japanese_date_to_date_type(japanese_date: str) -> datetime.date|None:
  """Convert str to datetime.date"""
  # Return if the date is not confirmed yet.
  if '日' not in japanese_date:
    return None

  year, month = japanese_date.split('年')
  month, day = month.split('月')
  day, _ = day.split('日')

  year = int(year)
  month = int(month)
  day = int(day)

  return datetime.date(year, month, day)


def main():
  goods_page = urlopen(config.YGO_GOOD_INFO_URL)
  if goods_page.getcode() == 200:
    goods_raw_data = goods_page.read().decode('utf-8')
    goods_matches = _goods_pattern.findall(goods_raw_data)

    yugioh_goods = goods_parse(goods_matches)
    private_key_id = os.environ['PRIVATE_KEY_ID']
    private_key = os.environ['PRIVATE_KEY'].replace('\\n','\n')
    client_email = os.environ['CLIENT_EMAIL']
    client_id = os.environ['CLIENT_ID']
    client_x509_cert_url = os.environ['CLIENT_URL']
    _config = {
      "type": "service_account",
      "project_id": "yugioh-goods-calendar",
      "private_key_id": private_key_id,
      "private_key": private_key,
      "client_email": client_email,
      "client_id": client_id,
      "auth_uri": "https://accounts.google.com/o/oauth2/auth",
      "token_uri": "https://oauth2.googleapis.com/token",
      "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
      "client_x509_cert_url": client_x509_cert_url,
      "universe_domain": "googleapis.com",
    }
    tmp_file = tempfile.NamedTemporaryFile(mode="w+")
    json.dump(_config, tmp_file)
    tmp_file.flush()
    service_account_file = tmp_file.name
    calendar_id = os.environ['CALENDAR_ID']
    calendar_handler = google_calendar_handler.GoogleCalendarHandler(
      service_account_file,
      calendar_id,
    )
    calendar_events = calendar_handler.get_all_calendar_event_summary()

    # Parse and create calendar events for each good
    for good in yugioh_goods:
      # End rule
      good_release_date_dt = convert_japanese_date_to_date_type(good.good_release_date)
      if not good_release_date_dt:
        print(f'{good.good_name} date is not confirmed yet, now is {good.good_release_date}, skip.')
        continue
      if good_release_date_dt < datetime.date.today():
        print('All unreleased goods\' are added!')
        break

      # Set short name of good if exist
      if good.good_type in config.TYPE_SHORTNAME_DICT:
        key = config.TYPE_SHORTNAME_DICT[good.good_type]
        good_order = _pack_list_per_type[key].index(good.good_name) + 1
        good.set_short_name(key, good_order)
      elif "ANIMATION CHRONICLE" in good.good_name:
        key = 'AC'
        good_order = _pack_list_per_type[key].index(good.good_name) + 1
        good.set_short_name(key, good_order)

      description = f'商品類型：{good.good_type}'
      card_list_url = find_card_list(good.good_name)
      if card_list_url:
        good.set_card_list_url(card_list_url)
        description += f'\n中文卡表：{good.card_list_url}'
      if good.good_url and '#' not in good.good_url:
        description += f'\n商品網址：{config.YGO_GOOD_INFO_URL }{good.good_url}'
      good.set_good_description(description)
      # Update only
      good_title = get_good_title(good)
      if good_title in calendar_events:
        print(f'Update calendar event for: {good_title}')
        calendar_handler.update_calendar_event(
          good_title,
          good.good_description,
        )
      else:
        print(f'Created calendar event for: {good_title}')
        calendar_handler.create_calendar_event(
          good_title,
          good.good_description,
          good_release_date_dt,
        )
      print('') # Print empty line
  else:
    print(f'Failed to get goods data: Status code {goods_page.response.status_code}')


if __name__ == '__main__':
    main()