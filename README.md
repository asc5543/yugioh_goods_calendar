# Yugioh Goods Calendar

## What is Yugioh Goods Calendar?
[Yugioh Goods Calendar](https://calendar.google.com/calendar/embed?src=a47600673f86110e900c56424e0c90c8e64578356255911796e624668948b058%40group.calendar.google.com&ctz=Asia%2FTokyo) is a calendar which update new goods information automatically.
![img_list](/img/Calendar_list.jpg)
![img_detail](/img/Calendar_detail.jpg)

## Background
I want to see the yugioh goods information on google calendar directly

## Design

We can separate the tool as three part:
* Parse good information
* Parse calendar information
* Create/Update calendar

In order to implement those functions, we need to
* Parse good information from Yugioh official website
* Control Google Calendar Events

### Parse good information
We can get the source code of the website by using urlopen.
The good information in source code of the Yugioh official website as the following:

    p[1]={"id":"cg2087","status":"new","class-name":"スペシャルパック","class-key":"special","title":"LIMITED PACK GX -  ラーイエロー -","thumbnail":"package/cg2087.png","price-intax":"3,600円","price-extax":" (本体価格 3,273円）","release-date":"2026年7月下旬","soon":"none","limited":'konamistyle-satellite',"url":"#cg2087","detail":"modal"};
	p[2]={"id":"cg2128","status":"new","class-name":"スペシャルパック","class-key":"special","title":"UTILITY SELECTION","thumbnail":"package/nowprinting.png","price-intax":"396円","price-extax":" (本体価格 360円）","release-date":"2026年8月8日(土)","soon":"あと105日","limited":'none',"url":"","detail":"none"};
	p[3]={"id":"cg2119","status":"","class-name":"基本パック","class-key":"basic","title":"BEYOND THE BRAVE","thumbnail":"package/nowprinting.png","price-intax":"198円","price-extax":" (本体価格 180円）","release-date":"2026年7月18日(土)","soon":"あと84日","limited":'none',"url":"","detail":"none"};
		

From the above source code, we can know the format of good is an dict with the following items:
* id
* class-name
* class-key
* title
* release-date
* url

#### Organize the same type pack (deprecated)
The short names like 1201, AC03, WPP3, TW02 are more famous for mentioning those packs.
In this parser, we would like to also implement it.
Some types will show the short name on the url item, but the url won’t appear if the content of the url is not ready.

Another method is that when we set the goods information, we also implement a list separate by type and sorted by release date, then we can know which is the first pack of this type.

    {'12': ['DUELIST NEXUS', 'AGE OF OVERLORD', 'PHANTOM NIGHTMARE', 'LEGACY OF DESTRUCTION', 'INFINITE FORBIDDEN', 'RAGE OF THE ABYSS', 'SUPREME DARKNESS', 'ALLIANCE INSIGHT'], 
     'WPP': ['WORLD PREMIERE PACK 2020', 'WORLD PREMIERE PACK 2021', 'WORLD PREMIERE PACK 2022', 'WORLD PREMIERE PACK 2023', 'WORLD PREMIERE PACK 2024'], 
     'AC': ['ANIMATION CHRONICLE 2021', 'ANIMATION CHRONICLE 2022', 'ANIMATION CHRONICLE 2023', 'ANIMATION CHRONICLE 2024'], 
     '11': ['RISE OF THE DUELIST', 'PHANTOM RAGE', 'BLAZING VORTEX', 'LIGHTNING OVERDRIVE', 'DAWN OF MAJESTY', 'BURST OF DESTINY', 'BATTLE OF CHAOS', 'DIMENSION FORCE', 'POWER OF THE ELEMENTS', 'DARKWING BLAST', 'PHOTON HYPERNOVA', 'CYBERSTORM ACCESS']}

### Google Calendar Handler
Uses google calendar API to parse existing events list.

### Create/Update calendar
Uses google calendar API to parse existing events list.

### Parse chinese card list from NTUCGM
Uses search function by good's name, parse the url from the result.

### Card-list lookup and backfill

`find_card_list()` returns a `CardListResult`, rather than a URL string:
`status` is `found`, `not_found`, `error`, or `ambiguous`. Only `found`
contains a verified `url`. Callers must check the status before updating links.
The calendar sync preserves existing card-list links when lookup is unsuccessful.

Search normalizes width, whitespace, case and dash characters, then tries the
full name, the name without the known 遊☆戯☆王 prefix, and aliases configured in
`config.CARD_LIST_ALIASES`. Years and variant suffixes are retained. Only card-list
articles with an exact normalized product heading are accepted; uncertain
matches are deliberately left unresolved. For translated or code-only card-list titles, the first ten body lines may
supply that heading. Explicit conflicting years or Latin product names are
rejected before inspecting the body. If metadata is insufficient, the article
body is fetched even when a nonempty description exists. This conservative rule may need
explicit aliases for differently translated titles.

Results are cached in `.cache/card_lists.json` (override with `CARD_LIST_CACHE`).
Matches expire after 30 days and absence after 6 hours. Errors and ambiguous
results are not cached. GitHub Actions restores and saves the file between runs.
Set `refresh=True` to bypass cached results when calling the function directly.

To sync one product even after its release date and bypass the lookup cache:

```sh
python yugioh_goods_parser.py --backfill-product '遊☆戯☆王 ORIGINAL ARTWORK COLLECTION'
```

This command writes to the configured Google Calendar and requires the same
credentials as the regular sync. The product must still be present in the
current official product listing. Other products are skipped.

Run offline tests (no calendar writes):

```sh
python -m unittest -v
```
