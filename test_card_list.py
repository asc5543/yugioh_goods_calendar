import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

import yugioh_goods_parser as parser

URL = 'https://ntucgm.blogspot.com/2026/05/original-artwork-collection-926.html'
NAME = '遊☆戯☆王 ORIGINAL ARTWORK COLLECTION'


def page(title, url=URL, **extra):
    return '<script type="application/ld+json">' + json.dumps({
        '@type': 'BlogPosting', 'headline': title,
        'mainEntityOfPage': {'@id': url}, **extra
    }) + '</script>'


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cache = Path(self.tmp.name) / 'cache.json'

    def search(self, name=NAME, **kwargs):
        return parser.find_card_list(name, cache_path=self.cache, **kwargs)

    def test_original_artwork_fixture_and_next_candidate(self):
        fixture = Path('tests/fixtures/original_artwork_search.html').read_text()
        with patch.object(parser, '_fetch_card_page', side_effect=['<html/>', fixture]) as fetch:
            result = self.search()
        self.assertEqual((result.status, result.url), ('found', URL))
        self.assertEqual(fetch.call_count, 2)

    def test_unmatched_results_do_not_stop_candidates(self):
        with patch.object(parser, '_fetch_card_page', side_effect=[
            page('[卡表資料] ANOTHER PACK', 'https://ntucgm.blogspot.com/2026/05/other.html'), page('[卡表資料] Original Artwork Collection 9/26發售')
        ]) as fetch:
            self.assertEqual(self.search().status, 'found')
        self.assertEqual(fetch.call_count, 2)

    def test_no_results_once_per_query(self):
        with patch.object(parser, '_fetch_card_page', return_value='<html/>') as fetch:
            self.assertEqual(self.search().status, 'not_found')
        self.assertEqual(fetch.call_count, 2)

    def test_normalization_preserves_version(self):
        self.assertEqual(parser.card_list_queries(' ＰＡＣＫ　２０２６ － A '), ['pack 2026 - a'])
        for title in ['[卡表資料] PACK 2025 9/26發售', '[卡表資料] PACK 2026 - B 9/26發售',
                      '[牌組介紹] PACK 2026 - A']:
            with self.subTest(title=title), patch.object(parser, '_fetch_card_page', return_value=page(title)):
                self.assertEqual(self.search('PACK 2026 - A', refresh=True).status, 'not_found')

    def test_multiple_matches_are_ambiguous_and_duplicates_deduplicated(self):
        title = '[卡表資料] ORIGINAL ARTWORK COLLECTION'
        with patch.object(parser, '_fetch_card_page', return_value=page(title) + page(title)):
            self.assertEqual(self.search().status, 'found')
        other = 'https://ntucgm.blogspot.com/2026/06/another.html'
        with patch.object(parser, '_fetch_card_page', return_value=page(title) + page(title, other)):
            result = self.search(refresh=True)
        self.assertEqual(result.status, 'ambiguous')
        self.assertEqual(len(result.candidates), 2)
        self.assertFalse(result.url)

    def test_errors_not_cached_or_treated_as_absence(self):
        with patch.object(parser, '_fetch_card_page', side_effect=URLError('offline')):
            self.assertEqual(self.search().status, 'error')
        self.assertFalse(self.cache.exists())

    def test_cache_refresh_and_expiry(self):
        with patch.object(parser, '_fetch_card_page', return_value=page('[卡表資料] ORIGINAL ARTWORK COLLECTION')) as fetch:
            self.search()
            self.search()
            self.assertEqual(fetch.call_count, 2)
            self.search(refresh=True)
            self.assertEqual(fetch.call_count, 4)
            with patch.object(parser.time, 'time', return_value=99999999999):
                self.search()
            self.assertEqual(fetch.call_count, 6)

    def test_configured_alias_and_ambiguity_not_cached(self):
        with patch.dict(parser.config.CARD_LIST_ALIASES, {'Official Name': ['別名']}), \
             patch.object(parser, '_fetch_card_page', side_effect=['', page('[卡表資料] 別名')]):
            self.assertEqual(self.search('Official Name').status, 'found')
        self.cache.unlink()
        title = '[卡表資料] ORIGINAL ARTWORK COLLECTION'
        with patch.object(parser, '_fetch_card_page', return_value=page(title) + page(title, 'https://ntucgm.blogspot.com/2026/05/second.html')):
            self.assertEqual(self.search().status, 'ambiguous')
        self.assertFalse(self.cache.exists())

    def test_partial_network_failure_does_not_claim_unique_match(self):
        with patch.object(parser, '_fetch_card_page', side_effect=[
            URLError('offline'), page('[卡表資料] ORIGINAL ARTWORK COLLECTION')
        ]):
            result = self.search()
        self.assertEqual(result.status, 'error')
        self.assertFalse(result.url)
        self.assertFalse(self.cache.exists())

    def test_absence_cache_expires(self):
        with patch.object(parser, '_fetch_card_page', return_value='') as fetch:
            self.search()
            self.search()
            self.assertEqual(fetch.call_count, 2)
            with patch.object(parser.time, 'time', return_value=99999999999):
                self.search()
            self.assertEqual(fetch.call_count, 4)

    def test_generic_title_body_fallback(self):
        with patch.object(parser, '_fetch_card_page', side_effect=[
            page('[卡表資料]'), page('[卡表資料]'),
            '<div class="post-body">2026/9/26 ORIGINAL ARTWORK COLLECTION<br/>卡片內容</div>'
        ]):
            self.assertEqual(self.search().status, 'found')

    def test_chinese_code_title_reads_body_despite_nonempty_summary(self):
        title = '[卡表資料] 海外包 WPP7卡表 6/27發售'
        with patch.object(parser, '_fetch_card_page', side_effect=[
            page(title, description='卡片效果與收錄資訊'),
            '<div class="post-body">2026/6/27 WORLD PREMIERE PACK 2026<br/>收錄資訊</div>'
        ]) as fetch:
            self.assertEqual(self.search('WORLD PREMIERE PACK 2026').status, 'found')
        self.assertEqual(fetch.call_args.args[0], URL)

    def test_conflicting_title_cannot_be_overridden_by_body(self):
        for title in ['[卡表資料] PACK 2025', '[卡表資料] PACK 2026 - B',
                      '[卡表資料] 海外包 2025', '[卡表資料] ANOTHER PACK']:
            with self.subTest(title=title), patch.object(parser, '_fetch_card_page', return_value=page(
                    title, articleBody='PACK 2026 - A')) as fetch:
                self.assertEqual(self.search('PACK 2026 - A', refresh=True).status, 'not_found')
                self.assertEqual(fetch.call_count, 1)

    def test_body_requires_heading_not_incidental_mention(self):
        for body in ['本商品與 WORLD PREMIERE PACK 2026 不同',
                     'WORLD PREMIERE PACK 2025',
                     '\n'.join(['其他內容'] * 10 + ['WORLD PREMIERE PACK 2026'])]:
            with self.subTest(body=body), patch.object(parser, '_fetch_card_page', side_effect=[
                page('[卡表資料] 海外包 WPP7卡表'), '<div class="post-body">' + body + '</div>'
            ]):
                self.assertEqual(self.search('WORLD PREMIERE PACK 2026', refresh=True).status, 'not_found')

    def test_translated_title_body_fetch_failure_is_error(self):
        with patch.object(parser, '_fetch_card_page', side_effect=[
            page('[卡表資料] 海外包 WPP7卡表'), URLError('offline')
        ]):
            self.assertEqual(self.search('WORLD PREMIERE PACK 2026').status, 'error')
        self.assertFalse(self.cache.exists())

    def test_rv02_entity_encoded_description(self):
        name = 'REVOLUTION BOOSTER － 方界・マリンセス・ゴーストリック －'
        body = '&#160; 2026/11/21 REVOLUTION BOOSTER&#65293;方界 &#12539; マリンセス &#12539; ゴーストリック&#65293;'
        url = 'https://ntucgm.blogspot.com/2026/07/rv02-1121.html'
        with patch.object(parser, '_fetch_card_page', return_value=page(
                '[卡表資料] RV02收錄卡表 11/21發售', url, description=body)) as fetch:
            result = self.search(name)
        self.assertEqual((result.status, result.url), ('found', url))
        self.assertEqual(fetch.call_count, 1)

    def test_rv02_inline_heading_body_fallback(self):
        name = 'REVOLUTION BOOSTER － 方界・マリンセス・ゴーストリック －'
        body = '<div class="post-body"><p>2026/11/21 REVOLUTION BOOSTER－方界<span>・</span><b>マリンセス</b><span>・</span>ゴーストリック－</p><p>價格：264日圓</p></div>'
        with patch.object(parser, '_fetch_card_page', side_effect=[
            page('[卡表資料] RV02收錄卡表 11/21發售'), body
        ]):
            self.assertEqual(self.search(name).status, 'found')
        other = body.replace('ゴーストリック', '別テーマ')
        self.assertFalse(parser._body_matches_product(other, parser.card_list_queries(name)))

    def test_json_graph_escaped_title_and_html_fallback(self):
        node = {'@type': 'BlogPosting', 'headline': '[卡表資料] PACK "A"',
                'mainEntityOfPage': {'@id': URL}, 'description': ''}
        html = '<script type="application/ld+json">' + json.dumps({'@graph': [node]}) + '</script>'
        self.assertEqual(parser._parse_card_articles(html)[0]['title'], '[卡表資料] PACK "A"')
        html = '<script type="application/ld+json">bad</script><h3 class="post-title"><a href="' + URL + '">[卡表資料] PACK</a></h3>'
        self.assertEqual(parser._parse_card_articles(html)[0]['url'], URL)

    @patch.object(parser.time, 'sleep')
    def test_retry_transient_error_and_timeout(self, sleep):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'ok'
        with patch.object(parser, 'urlopen', side_effect=[HTTPError(URL, 429, 'limited', {'Retry-After': '2'}, None), response]) as fetch:
            self.assertEqual(parser._fetch_card_page(URL), 'ok')
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(fetch.call_args.kwargs['timeout'], 20)
        with patch.object(parser, 'urlopen', side_effect=HTTPError(URL, 404, 'missing', {}, None)) as fetch:
            with self.assertRaises(HTTPError):
                parser._fetch_card_page(URL)
            self.assertEqual(fetch.call_count, 1)

    def test_preserve_existing_link_for_all_unsuccessful_statuses(self):
        old = 'Type: old\nCard List (CH): ' + URL
        for status in ['not_found', 'error', 'ambiguous']:
            with self.subTest(status=status):
                result = parser.CardListResult(status)
                description = 'Type: new'
                if result.status == 'found':
                    description += '\nCard List (CH): ' + result.url
                self.assertIn(URL, parser.preserve_card_list(description, old))
        new = 'Type: new\nCard List (CH): https://example.com/new'
        self.assertEqual(parser.preserve_card_list(new, old), new)

    def test_reject_known_wrong_link_only_for_affected_product(self):
        name = 'Yu-Gi-Oh! THE DARK SIDE OF DIMENSIONS 10th ANNIVERSARY MOVIE'
        wrong = 'https://ntucgm.blogspot.com/2019/05/asia-championship-regional-qualifier.html'
        old = 'Type: old\nCard List (CH): ' + wrong
        self.assertEqual(parser.preserve_card_list('Type: new', old, name), 'Type: new')
        self.assertIn(wrong, parser.preserve_card_list('Type: new', old, 'Other product'))
        self.assertIn(URL, parser.preserve_card_list('Type: new', 'Card List (CH): ' + URL, name))

    def test_rejected_cached_link_is_not_returned(self):
        name = 'Yu-Gi-Oh! THE DARK SIDE OF DIMENSIONS 10th ANNIVERSARY MOVIE'
        wrong = 'https://ntucgm.blogspot.com/2019/05/asia-championship-regional-qualifier.html'
        key = json.dumps(['body-match-v3', *parser.card_list_queries(name)], ensure_ascii=False)
        self.cache.write_text(json.dumps({key: {'status': 'found', 'url': wrong, 'expires': 99999999999}}))
        with patch.object(parser, '_fetch_card_page', return_value=page('[上位專訪] 冠軍', wrong)) as fetch:
            self.assertEqual(self.search(name).status, 'not_found')
        fetch.assert_called_once()

    def test_released_product_backfill_integration(self):
        raw = 'p[1]={"title":"' + NAME + '","class-name":"special","release-date":"2020年9月26日(土)","url":"yac1"};'
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.getcode.return_value = 200
        response.read.return_value = raw.encode()
        handler = Mock()
        handler.get_all_calendar_event_summary.return_value = [NAME]
        handler.get_calendar_event_by_summary.return_value = {'description': 'Card List (CH): ' + URL}
        with patch.object(parser, 'urlopen', return_value=response), \
             patch.object(parser.google_api_handler, 'generate_account_json_file', return_value='unused'), \
             patch.object(parser.google_api_handler, 'GoogleCalendarHandler', return_value=handler), \
             patch.object(parser.os, 'unlink'), patch.dict(parser.os.environ, {'CALENDAR_ID': 'test'}), \
             patch.object(parser, 'find_card_list', return_value=parser.CardListResult('error')) as search:
            parser.main()
            search.assert_not_called()
            parser.main(backfill_product=NAME)
            search.assert_called_once_with(NAME, refresh=True)
            self.assertIn(URL, handler.update_calendar_event.call_args.args[1])
            handler.create_calendar_event.assert_not_called()


if __name__ == '__main__':
    unittest.main()
