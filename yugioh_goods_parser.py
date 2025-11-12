import time
import random
from bs4 import BeautifulSoup
from config import config
from lib import google_api_handler
from lib import yugioh_good

import datetime
import os
import re

from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen, Request

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
  user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 Firefox/54.0',
  ]

  goods_name_list = [goods_name]

  if '-' in goods_name:
    for good_name in goods_name.split('-'):
      goods_name_list.append(good_name)

  # TODO: Refactor the retry and name find logic
  for name in goods_name_list:
    name = name.strip()
    print(f'Find "{name}" on website')
    ntucgm_url = r"https://ntucgm.blogspot.com/search?q=" + quote(name)

    retry = 0
    while retry < config.MAX_RETRY:
      try:
        time.sleep(random.uniform(1, 3))

        headers = {'User-Agent': random.choice(user_agents)}
        req = Request(ntucgm_url, headers=headers)

        search_page = urlopen(req)

        content = search_page.read().decode('utf-8')
        soup = BeautifulSoup(content, 'html.parser')
        script_tags = soup.find_all('script', type='application/ld+json')
        if not script_tags:
          if name == goods_name_list[-1].strip():
            print('No card list exist!!')
            return ""
          else:
            print(f'No match "{name}" found on website, try next name')
            continue
        for script_tag in script_tags:
          target_title = ''

          script_content = script_tag.string.strip()
          match_title = re.search(r'"headline":\s*"([^"]+)"', script_content)
          if match_title:
            target_title = match_title.group(1)
            print(f'title: {target_title}')
            # If more than 1 result, check the title
            if name not in target_title and len(script_tags) > 1:
              print(f'{name} not in the title {target_title}, try next one')
              continue
          match = re.search(r'"@id":\s*"([^"]+)"', script_content)

          if match:
            url = match.group(1)
            print(f'Card list: {url}')
            return url
          else:
            print('No match found')
            return ""

      except HTTPError as e:
        if e.code == 429:
          print(f'HTTP Error 429: Too Many Requests for "{goods_name}". Retrying after a longer delay.')
          # Wait long for HTTP Error 429
          time.sleep(15)
          retry += 1
        else:
          # Throw exception for other error
          print(f'HTTP Error {e.code} for "{goods_name}": {e.reason}')
          return ""
      except Exception as e:
        print(f"Error fetching page for {goods_name}: {e}")
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
    service_account_file = google_api_handler.generate_account_json_file("yugioh-goods-calendar")
    calendar_id = os.environ['CALENDAR_ID']
    calendar_handler = google_api_handler.GoogleCalendarHandler(
      service_account_file,
      calendar_id,
    )
    os.unlink(service_account_file)
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