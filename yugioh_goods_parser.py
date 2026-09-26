import argparse
import ast
import json
import logging
import unicodedata
from dataclasses import dataclass
from pathlib import Path
import datetime
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from config import config
from lib import google_api_handler, yugioh_good

load_dotenv()
logger = logging.getLogger(__name__)

# Goods Pattern: Capturing the content inside curly braces {}
_goods_pattern = re.compile(r'p\[\d+\]\s*=\s*(\{.+?\});')

# Dictionary to track the order of goods within the same type
# e.g., RAGE OF THE ABYSS is 1206, ANIMATION CHRONICLE 2024 is AC04
_pack_list_per_type = {}


@dataclass(frozen=True)
class CardListResult:
    """Only a unique, verified match carries a URL."""
    status: str
    url: str = ''
    candidates: tuple[str, ...] = ()
    reason: str = ''


def normalize_name(value: str) -> str:
    value = unicodedata.normalize('NFKC', value).casefold()
    value = re.sub(r'[‐‑‒–—−－]', '-', value)
    value = re.sub(r'\s*-\s*', ' - ', value)
    return re.sub(r'\s+', ' ', value).strip()


def card_list_queries(goods_name: str) -> list[str]:
    full = normalize_name(goods_name)
    short = re.sub(r'^遊[☆★]戯[☆★]王\s*', '', full)
    aliases = getattr(config, 'CARD_LIST_ALIASES', {}).get(goods_name, [])
    # Never split on hyphens: a suffix may identify a different product.
    return list(dict.fromkeys(q for q in [full, short, *map(normalize_name, aliases)] if q))


def _article_url(value: str) -> str:
    if not isinstance(value, str):
        return ''
    parts = urlsplit(value)
    if (parts.scheme in ('http', 'https')
            and parts.hostname == 'ntucgm.blogspot.com'
            and re.fullmatch(r'/\d{4}/\d{2}/[^/]+\.html', parts.path)):
        return 'https://ntucgm.blogspot.com' + parts.path
    return ''


def _fetch_card_page(url: str) -> str:
    attempts = max(1, config.MAX_RETRY)
    for attempt in range(attempts):
        try:
            time.sleep(1)
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as response:
                return response.read().decode('utf-8')
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            transient = not isinstance(error, HTTPError) or error.code in (408, 429, 500, 502, 503, 504)
            if not transient or attempt == attempts - 1:
                raise
            delay = min(2 ** (attempt + 1), 30)
            if isinstance(error, HTTPError):
                retry_after = error.headers.get('Retry-After', '') if error.headers else ''
                if retry_after.isdigit():
                    delay = min(int(retry_after), 60)
            logger.warning('Retrying %s after %s: %ss', url, error, delay)
            time.sleep(delay)
    raise RuntimeError('No fetch attempt made')


def _parse_card_articles(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    articles = {}

    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            kind = node.get('@type', [])
            kind = [kind] if isinstance(kind, str) else (kind or [])
            if 'BlogPosting' in kind or 'Article' in kind:
                entity = node.get('mainEntityOfPage', {})
                url = entity.get('@id', '') if isinstance(entity, dict) else entity
                url = _article_url(url or node.get('url', '') or node.get('@id', ''))
                if url:
                    articles[url] = {'url': url, 'title': node.get('headline') or '',
                                     'body': node.get('articleBody') or node.get('description') or ''}
            if '@graph' in node:
                visit(node['@graph'])

    for script in soup.find_all('script', type='application/ld+json'):
        try:
            visit(json.loads(script.get_text()))
        except (ValueError, TypeError):
            logger.warning('Skipping malformed JSON-LD')
    # Blogger templates may omit structured data on search pages.
    for heading in soup.select('.post-title, .entry-title'):
        link = heading.find('a', href=True)
        if link:
            url = _article_url(link['href'])
            if url:
                articles.setdefault(url, {'url': url, 'title': heading.get_text(' ', strip=True), 'body': ''})
    return list(articles.values())


def _matches_product(text: str, names: list[str]) -> bool:
    # Compare the product heading, retaining years, versions and hyphen suffixes.
    text = normalize_name(BeautifulSoup(text, 'html.parser').get_text(' ', strip=True))
    text = re.sub(r'^\[卡表資料\]\s*', '', text)
    text = re.sub(r'^遊[☆★]戯[☆★]王\s*', '', text)
    text = re.sub(r'^\d{4}[/-]\d{1,2}[/-]\d{1,2}\s*', '', text)
    text = re.sub(r'\s*\d{1,2}/\d{1,2}\s*(?:發售|発売).*$' , '', text).strip()
    return text in names


def _title_allows_body_check(title: str, names: list[str]) -> bool:
    """Allow translated/code-only titles, but reject conflicting years/names."""
    title = normalize_name(title).replace('[卡表資料]', '').strip()
    title = re.sub(r'\s*\d{1,2}/\d{1,2}\s*(?:發售|発売).*$', '', title)
    expected_years = set(re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', ' '.join(names)))
    title_years = set(re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', title))
    if expected_years and title_years and not title_years <= expected_years:
        return False
    # Codes such as WPP7/1303 are insufficient evidence either way. A spelled
    # out Latin product name, however, must not be overridden by body mentions.
    words = re.findall(r'(?<![a-z0-9])[a-z]{2,}(?![a-z0-9])', title)
    name_words = set(re.findall(r'[a-z]{2,}', ' '.join(names)))
    return len(words) < 2 and not name_words.intersection(words)


def _body_matches_product(body: str, names: list[str]) -> bool:
    soup = BeautifulSoup(body, 'html.parser')
    lines = soup.get_text('\n', strip=True).splitlines()
    return any(_matches_product(line, names) for line in lines[:10])


def _read_search_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def find_card_list(goods_name: str, *, refresh: bool = False,
                   cache_path: str | Path | None = None) -> CardListResult:
    """Search all precise aliases; do not confuse absence with fetch failure.

    Success is cached for 30 days, absence for 6 hours. Errors and ambiguous
    results are never cached. Set refresh=True for explicit backfills.
    """
    names = card_list_queries(goods_name)
    if not names:
        return CardListResult('not_found', reason='Empty product name')
    path = Path(cache_path or os.environ.get('CARD_LIST_CACHE', '.cache/card_lists.json'))
    cache = _read_search_cache(path)
    key = json.dumps(['body-match-v2', *names], ensure_ascii=False)
    entry = cache.get(key, {})
    if not refresh and isinstance(entry, dict):
        expires = entry.get('expires', 0)
        if isinstance(expires, (int, float)) and expires > time.time():
            if entry.get('status') == 'not_found':
                return CardListResult('not_found', reason='Cached absence')
            url = _article_url(entry.get('url', ''))
            if entry.get('status') == 'found' and url:
                return CardListResult('found', url, reason='Cached match')

    articles = {}
    errors = []
    for name in names:
        url = 'https://ntucgm.blogspot.com/search?q=' + quote(name)
        logger.info('Searching card list: %s', name)
        try:
            for article in _parse_card_articles(_fetch_card_page(url)):
                articles.setdefault(article['url'], article)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            errors.append(str(error))
            logger.warning('Search failed for %s: %s', name, error)

    matches = []
    for url, article in articles.items():
        # A deck guide mentioning the product is not a card list.
        if '[卡表資料]' not in normalize_name(article['title']):
            continue
        if _matches_product(article['title'], names):
            matches.append(url)
            continue
        if not _title_allows_body_check(article['title'], names):
            continue
        # Search descriptions may be truncated or omit the product heading.
        # Always fall back to the actual article when metadata is insufficient.
        if _body_matches_product(article['body'], names):
            matches.append(url)
            continue
        try:
            soup = BeautifulSoup(_fetch_card_page(url), 'html.parser')
            node = soup.select_one('.post-body, .entry-content')
            if node and _body_matches_product(str(node), names):
                matches.append(url)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            errors.append(str(error))

    if len(matches) > 1:
        result = CardListResult('ambiguous', candidates=tuple(sorted(matches)), reason='Multiple matching articles')
    elif errors:
        # An incomplete search cannot establish uniqueness or definite absence.
        result = CardListResult('error', candidates=tuple(matches), reason='; '.join(errors))
    elif matches:
        result = CardListResult('found', matches[0], reason='Unique product heading match')
    else:
        result = CardListResult('not_found', reason='No matching card-list article')
    logger.info('Card list %s: %s (%s)', goods_name, result.status, result.reason)
    if result.status in ('found', 'not_found'):
        cache[key] = {'status': result.status, 'url': result.url,
                      'expires': time.time() + (30 * 86400 if result.url else 6 * 3600)}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(cache, ensure_ascii=False), encoding='utf-8')
            temporary.replace(path)
        except OSError as error:
            logger.warning('Could not save card-list cache: %s', error)
    return result


def preserve_card_list(description: str, existing: str) -> str:
    """A failed lookup must not remove an existing calendar link."""
    if not re.search(r'^Card List \(CH\):', description, re.M):
        previous = re.search(r'^Card List \(CH\):[^\r\n]+', existing, re.M)
        if previous:
            description += '\n' + previous.group(0)
    return description


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


def main(backfill_product: str | None = None):
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
                if backfill_product and normalize_name(good.good_name) != normalize_name(backfill_product):
                    continue
                if not release_dt or (release_dt < datetime.date.today() and not backfill_product):
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
                result = find_card_list(good.good_name, refresh=bool(backfill_product))
                if result.status == 'found':
                    good.set_card_list_url(result.url)
                    desc += f'\nCard List (CH): {good.card_list_url}'
                if good.good_url and '#' not in good.good_url:
                    desc += f'\nURL: {config.YGO_GOOD_INFO_URL}{good.good_url}'
                good.set_good_description(desc)

                title = get_good_title(good)
                if title in calendar_events:
                    print(f'Updating event: {title}')
                    existing = handler.get_calendar_event_by_summary(title)
                    description = preserve_card_list(good.good_description, existing.get('description', ''))
                    handler.update_calendar_event(title, description)
                else:
                    print(f'Creating event: {title}')
                    handler.create_calendar_event(
                        title, good.good_description, release_dt
                    )
    except Exception as e:
        print(f"Runtime error: {e}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('--backfill-product', help='Exact official product name; include released products and bypass cache')
    args = parser.parse_args()
    main(backfill_product=args.backfill_product)
