# Yugioh Goods Calendar

## What is Yugioh Goods Calendar?
[Yugioh Goods Calendar](https://calendar.google.com/calendar/embed?src=a47600673f86110e900c56424e0c90c8e64578356255911796e624668948b058%40group.calendar.google.com&ctz=Asia%2FTokyo) is a calendar which update new goods information automatically.


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

    p[1]={"id":"cg2010","status":"new","class-name":"コンセプトパック","class-key":"concept","type":"デッキビルドパック","title":"デッキビルドパック ジャスティス・ハンターズ","thumbnail":"package/nowprinting.png","price-intax":"176円","price-extax":" (本体価格 160円）","release-date":"2025年3月22日(土)","soon":"あと94日","limited":'none',"url":"","detail":"none"};
    p[2]={"id":"cg2004","status":"","class-name":"スペシャルパック","class-key":"special","type":"25周年記念","title":"QUARTER CENTURY ART COLLECTION","thumbnail":"package/nowprinting.png","price-intax":"385円","price-extax":" (本体価格 350円）","release-date":"2025年2月22日(土)","soon":"あと66日","limited":'none',"url":"","detail":"none"};
    p[3]={"id":"cg2002","status":"","class-name":"基本パック","class-key":"basic","type":"基本パック12","title":"ALLIANCE INSIGHT","thumbnail":"package/cg2002-pack.png","price-intax":"1パック 176円","price-extax":" (本体価格 160円）","release-date":"2025年1月25日(土)","soon":"あと38日","limited":'none',"url":"alin","detail":"page"};

From the above source code, we can know the format of good is an dict with the following items:
* id
* type
* title
* release-date
* url

#### Organize the same type pack
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
