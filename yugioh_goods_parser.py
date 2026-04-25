import ast
import datetime
import os
import random
import re
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from config import config
from lib import google_api_handler, yugioh_good

load_dotenv()

# Goods Pattern: Capturing the content inside curly braces {}
_goods_pattern = re.compile(r'p\[\d+\]\s*=\s*(\{.+?\});')

# Dictionary to track the order of goods within the same type
# e.g., RAGE OF THE ABYSS is 1206, ANIMATION CHRONICLE 2024 is AC04
_pack_list_per_type = {}


def find_card_list(goods_name: str) -> str | None:
    """Fetch the card list URL from ntucgm blog."""
    user_agents = [
        ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
         '(KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'),
        ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36 '
         '(KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36'),
        ('Mozilla/5.0 (Windows NT 6.1; WOW64; rv:54.0) Gecko/20100101 '
         'Firefox/54.0'),
    ]

    goods_name_list = [goods_name]

    if '-' in goods_name:
        goods_name_list.extend(
            [name.strip() for name in goods_name.split('-')]
        )

    for name in goods_name_list:
        name = name.strip()
        print(f'Searching for "{name}" on website...')
        ntucgm_url = "https://ntucgm.blogspot.com/search?q=" + quote(name)

        retry = 0
        while retry < config.MAX_RETRY:
            try:
                time.sleep(random.uniform(1, 3))

                headers = {'User-Agent': random.choice(user_agents)}
                req = Request(ntucgm_url, headers=headers)

                with urlopen(req) as search_page:
                    content = search_page.read().decode('utf-8')
                    soup = BeautifulSoup(content, 'html.parser')
                    script_tags = soup.find_all(
                        'script', type='application/ld+json'
                    )

                if not script_tags:
                    if name == goods_name_list[-1].strip():
                        print('No card list exists!')
                        return ""
                    print(f'No match for "{name}", trying next...')
                    continue

                for script_tag in script_tags:
                    script_content = script_tag.string.strip()
                    match_title = re.search(
                        r'"headline":\s*"([^"]+)"', script_content
                    )

                    if match_title:
                        target_title = match_title.group(1)
                        print(f'Found title: {target_title}')
                        if name not in target_title and len(script_tags) > 1:
                            continue

                    match = re.search(r'"@id":\s*"([^"]+)"', script_content)
                    if match:
                        url = match.group(1)
                        print(f'Card list URL: {url}')
                        return url
                return ""

            except HTTPError as e:
                if e.code == 429:
                    print('HTTP 429: Rate limited. Retrying...')
                    time.sleep(15)
                    retry += 1
                else:
                    print(f'HTTP Error {e.code}: {e.reason}')
                    return ""
            except Exception as e:
                print(f"Error fetching page: {e}")
                return ""


def goods_parse(goods_matches: list[str]) -> list[yugioh_good.YugiohGoods]:
    """Process raw match strings into a list of YugiohGoods objects."""
    goods_list = []
    for good_str in goods_matches:
        good = good_parse_good_str(good_str)
        if not good:
            continue

        if good.good_type in config.TYPE_SHORTNAME_DICT:
            key = config.TYPE_SHORTNAME_DICT[good.good_type]
            _pack_list_per_type.setdefault(key, []).append(good.good_name)
        elif "ANIMATION CHRONICLE" in good.good_name:
            _pack_list_per_type.setdefault('AC', []).append(good.good_name)
        goods_list.append(good)

    for key in _pack_list_per_type:
        _pack_list_per_type[key].reverse()

    return goods_list


def good_parse_good_str(good_str: str) -> yugioh_good.YugiohGoods | None:
    """Parse the JS object string using ast.literal_eval."""
    try:
        data = ast.literal_eval(good_str)
        return yugioh_good.YugiohGoods(
            good_name=data.get("title", ""),
            good_type=data.get("class-name", ""),
            good_release_date=data.get("release-date", ""),
            good_url=data.get("url", "")
        )
    except Exception as e:
        print(f"Failed to parse item: {e}")
        return None


def get_good_title(good: yugioh_good.YugiohGoods) -> str:
    """Get the full title including short name if available."""
    if good.good_short_name:
        return f'[{good.good_short_name}] {good.good_name}'
    return good.good_name


def convert_japanese_date_to_date_type(
    japanese_date: str
) -> datetime.date | None:
    """Convert Japanese date string to datetime.date."""
    if '日' not in japanese_date:
        return None

    try:
        year, month_part = japanese_date.split('年')
        month, day_part = month_part.split('月')
        day = day_part.split('日')[0]
        return datetime.date(int(year), int(month), int(day))
    except (ValueError, IndexError):
        return None


def main():
    """Main execution flow for syncing YGO goods to Google Calendar."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = Request(config.YGO_GOOD_INFO_URL, headers=headers)

    try:
        with urlopen(req) as response:
            if response.getcode() != 200:
                print(f'Failed to fetch data: HTTP {response.getcode()}')
                return

            goods_raw_data = response.read().decode('utf-8')
            goods_matches = _goods_pattern.findall(goods_raw_data)

            print(f"Found {len(goods_matches)} raw data entries.")
            yugioh_goods = goods_parse(goods_matches)

            proj_id = os.environ.get('PROJECT_ID', 'yugioh-goods-calendar')
            svc_acc_file = google_api_handler.generate_account_json_file(
                proj_id)
            cal_id = os.environ['CALENDAR_ID']
            handler = google_api_handler.GoogleCalendarHandler(
                svc_acc_file, cal_id
            )
            os.unlink(svc_acc_file)
            calendar_events = handler.get_all_calendar_event_summary()

            for good in yugioh_goods:
                release_dt = convert_japanese_date_to_date_type(
                    good.good_release_date
                )
                if not release_dt or release_dt < datetime.date.today():
                    continue

                # Handle short name logic
                key = None
                if good.good_type in config.TYPE_SHORTNAME_DICT:
                    key = config.TYPE_SHORTNAME_DICT[good.good_type]
                elif "ANIMATION CHRONICLE" in good.good_name:
                    key = 'AC'

                if key and good.good_name in _pack_list_per_type.get(key, []):
                    order = _pack_list_per_type[key].index(good.good_name) + 1
                    good.set_short_name(key, order)

                # Build description and sync
                desc = f'Type: {good.good_type}'
                card_list_url = find_card_list(good.good_name)
                if card_list_url:
                    good.set_card_list_url(card_list_url)
                    desc += f'\nCard List (CH): {good.card_list_url}'
                if good.good_url and '#' not in good.good_url:
                    desc += f'\nURL: {config.YGO_GOOD_INFO_URL}{good.good_url}'
                good.set_good_description(desc)

                title = get_good_title(good)
                if title in calendar_events:
                    print(f'Updating event: {title}')
                    handler.update_calendar_event(title, good.good_description)
                else:
                    print(f'Creating event: {title}')
                    handler.create_calendar_event(
                        title, good.good_description, release_dt
                    )
    except Exception as e:
        print(f"Runtime error: {e}")


if __name__ == '__main__':
    main()
