YGO_GOOD_INFO_URL = 'https://www.yugioh-card.com/japan/products/'
TYPE_SHORTNAME_DICT = {
  "ワールドプレミアム": "WPP",
  "基本パック11": "11",
  "基本パック12": "12",
  "基本パック13": "13",
}
MAX_RETRY = 5

# Exact official product name -> verified alternative product names.
CARD_LIST_ALIASES = {}

# Confirmed incorrect historical matches, scoped to the exact product.
CARD_LIST_REJECTED_URLS = {
    'Yu-Gi-Oh! THE DARK SIDE OF DIMENSIONS 10th ANNIVERSARY MOVIE': {
        'https://ntucgm.blogspot.com/2019/05/asia-championship-regional-qualifier.html',
    },
}
