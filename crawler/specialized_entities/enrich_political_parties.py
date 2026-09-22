"""
Enriched Political Parties of Bangladesh — 48 entries
Fields: entity_id, name_bn, name_en, acronym, founded_year, current_head_bn, ideology_summary_bn, wiki_image_url, category
"""

import csv, os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw", "enriched")
os.makedirs(DATA_DIR, exist_ok=True)

PARTIES = [
    {
        "entity_id": "pol_01",
        "name_bn": "বাংলাদেশ আওয়ামী লীগ",
        "name_en": "Bangladesh Awami League",
        "acronym": "AL",
        "founded_year": "1949",
        "current_head_bn": "শেখ হাসিনা",
        "ideology_summary_bn": "বাংলাদেশ আওয়ামী লীগ একটি মধ্য-বাম ধর্মনিরপেক্ষ দল। এটি বাঙালি জাতীয়তাবাদ, সমাজতন্ত্র ও ধর্মনিরপেক্ষতার আদর্শে প্রতিষ্ঠিত। ১৯৭১ সালের মুক্তিযুদ্ধে নেতৃত্বদানকারী দল হিসেবে এর ঐতিহাসিক গুরুত্ব অপরিসীম।",
        "wiki_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Awami_League_logo.svg/200px-Awami_League_logo.svg.png",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_02",
        "name_bn": "বাংলাদেশ জাতীয়তাবাদী দল",
        "name_en": "Bangladesh Nationalist Party",
        "acronym": "BNP",
        "founded_year": "1978",
        "current_head_bn": "খালেদা জিয়া",
        "ideology_summary_bn": "বিএনপি বাংলাদেশি জাতীয়তাবাদ ও রক্ষণশীল ইসলামি মূল্যবোধের সমন্বয়ে গঠিত একটি কেন্দ্র-ডানপন্থী দল। জিয়াউর রহমান কর্তৃক প্রতিষ্ঠিত এই দল বাজার অর্থনীতি ও পশ্চিমা সম্পর্ক রক্ষার পক্ষে।",
        "wiki_image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/BNP_logo.svg/200px-BNP_logo.svg.png",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_03",
        "name_bn": "জাতীয় পার্টি (এরশাদ)",
        "name_en": "Jatiya Party (Ershad)",
        "acronym": "JP",
        "founded_year": "1986",
        "current_head_bn": "জি এম কাদের",
        "ideology_summary_bn": "জাতীয় পার্টি একটি কেন্দ্রপন্থী দল যা হুসেইন মুহম্মদ এরশাদ কর্তৃক প্রতিষ্ঠিত। দলটি জাতীয়তাবাদ ও ইসলামি মূল্যবোধের মিশ্রণে রাজনীতি করে এবং 'তৃতীয় শক্তি' হিসেবে নিজেকে উপস্থাপন করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_04",
        "name_bn": "বাংলাদেশ জামায়াতে ইসলামী",
        "name_en": "Bangladesh Jamaat-e-Islami",
        "acronym": "BJI",
        "founded_year": "1941",
        "current_head_bn": "শফিকুর রহমান",
        "ideology_summary_bn": "জামায়াতে ইসলামী বাংলাদেশের প্রধান ইসলামপন্থী দল। দলটি ইসলামি রাষ্ট্র প্রতিষ্ঠা এবং শরিয়া আইনের ভিত্তিতে সমাজ গড়ার পক্ষে। ১৯৭১ সালের মুক্তিযুদ্ধে বিতর্কিত ভূমিকার কারণে দলটি সমালোচিত।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_05",
        "name_bn": "বাংলাদেশের কমিউনিস্ট পার্টি",
        "name_en": "Communist Party of Bangladesh",
        "acronym": "CPB",
        "founded_year": "1948",
        "current_head_bn": "মুজাহিদুল ইসলাম সেলিম",
        "ideology_summary_bn": "বাংলাদেশের কমিউনিস্ট পার্টি মার্কসবাদ-লেনিনবাদের আদর্শ অনুসরণ করে। দলটি শ্রমিক শ্রেণির অধিকার, ভূমি সংস্কার এবং সাম্রাজ্যবাদবিরোধী আন্দোলনে সক্রিয় ভূমিকা পালন করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_06",
        "name_bn": "জাতীয় সমাজতান্ত্রিক দল (জাসদ)",
        "name_en": "Jatiya Samajtantrik Dal",
        "acronym": "JSD",
        "founded_year": "1972",
        "current_head_bn": "হাসানুল হক ইনু",
        "ideology_summary_bn": "জাসদ মুক্তিযুদ্ধের পরপরই প্রতিষ্ঠিত একটি বাম-ঘরানার দল। দলটি বৈজ্ঞানিক সমাজতন্ত্র ও সাম্রাজ্যবাদবিরোধী রাজনীতির পক্ষে অবস্থান নেয়। বর্তমানে দলটি বেশ কয়েকটি ভাগে বিভক্ত।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_07",
        "name_bn": "বাংলাদেশের ওয়ার্কার্স পার্টি",
        "name_en": "Workers Party of Bangladesh",
        "acronym": "WPB",
        "founded_year": "1980",
        "current_head_bn": "রাশেদ খান মেনন",
        "ideology_summary_bn": "ওয়ার্কার্স পার্টি মার্কসবাদী আদর্শে বিশ্বাসী একটি বামপন্থী দল। দলটি শ্রমিক-কৃষকের মুক্তি, সাম্রাজ্যবাদবিরোধিতা এবং একটি অসাম্প্রদায়িক বাংলাদেশ গড়ার লক্ষ্যে কাজ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_08",
        "name_bn": "ইসলামী আন্দোলন বাংলাদেশ",
        "name_en": "Islami Andolan Bangladesh",
        "acronym": "IAB",
        "founded_year": "1987",
        "current_head_bn": "সৈয়দ মুহাম্মদ রেজাউল করীম",
        "ideology_summary_bn": "ইসলামী আন্দোলন বাংলাদেশ একটি ইসলামপন্থী রাজনৈতিক দল যা চরমোনাই পীরের অনুসারীদের নিয়ে গঠিত। দলটি ইসলামি শাসনব্যবস্থা কায়েম ও সুদমুক্ত অর্থনীতি প্রতিষ্ঠার দাবিতে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_09",
        "name_bn": "লিবারেল ডেমোক্রেটিক পার্টি",
        "name_en": "Liberal Democratic Party",
        "acronym": "LDP",
        "founded_year": "2006",
        "current_head_bn": "কর্নেল (অব.) অলি আহমদ",
        "ideology_summary_bn": "লিবারেল ডেমোক্রেটিক পার্টি একটি উদার গণতান্ত্রিক দল যা বিএনপি থেকে বিভক্ত হয়ে গঠিত হয়েছে। দলটি মুক্তবাজার অর্থনীতি ও বহুদলীয় গণতন্ত্রের পক্ষে অবস্থান নেয়।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_10",
        "name_bn": "গণফোরাম",
        "name_en": "Gono Forum",
        "acronym": "GF",
        "founded_year": "1993",
        "current_head_bn": "কামাল হোসেন",
        "ideology_summary_bn": "গণফোরাম একটি মধ্যপন্থী সামাজিক গণতান্ত্রিক দল যা ড. কামাল হোসেন প্রতিষ্ঠা করেন। দলটি সুশাসন, দুর্নীতিমুক্ত প্রশাসন এবং সাংবিধানিক গণতন্ত্র প্রতিষ্ঠার পক্ষে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_11",
        "name_bn": "বাংলাদেশ ন্যাশনাল আওয়ামী পার্টি (ভাসানী ন্যাপ)",
        "name_en": "Bangladesh National Awami Party (Bhashani NAP)",
        "acronym": "NAP",
        "founded_year": "1957",
        "current_head_bn": "",
        "ideology_summary_bn": "মাওলানা ভাসানীর নেতৃত্বে গঠিত ন্যাপ বাংলাদেশের কৃষক ও মেহনতি মানুষের স্বার্থে রাজনীতি করত। দলটি সাম্রাজ্যবাদবিরোধী ও চীনপন্থী সমাজতান্ত্রিক আদর্শ ধারণ করত।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_12",
        "name_bn": "বাংলাদেশ কৃষক-শ্রমিক আওয়ামী লীগ (বাকশাল)",
        "name_en": "Bangladesh Krishak Sramik Awami League",
        "acronym": "BAKSAL",
        "founded_year": "1975",
        "current_head_bn": "",
        "ideology_summary_bn": "বাকশাল শেখ মুজিবুর রহমানের নেতৃত্বে ১৯৭৫ সালে প্রতিষ্ঠিত একটি একদলীয় সমাজতান্ত্রিক সংগঠন। এটি বাংলাদেশে স্বল্পস্থায়ী একদলীয় শাসনের প্রতীক।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_13",
        "name_bn": "বাংলাদেশ ইসলামী ফ্রন্ট",
        "name_en": "Bangladesh Islami Front",
        "acronym": "BIF",
        "founded_year": "1987",
        "current_head_bn": "মাওলানা এম. এ. মান্নান",
        "ideology_summary_bn": "বাংলাদেশ ইসলামী ফ্রন্ট একটি ইসলামি মূল্যবোধভিত্তিক রাজনৈতিক দল যা ইসলামি সমাজ প্রতিষ্ঠার লক্ষ্যে গঠিত। দলটি সুফি ধারায় বিশ্বাসী এবং শান্তিপূর্ণ রাজনৈতিক পথ অনুসরণ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_14",
        "name_bn": "বাংলাদেশ খেলাফত মজলিস",
        "name_en": "Bangladesh Khelafat Majlis",
        "acronym": "BKM",
        "founded_year": "1989",
        "current_head_bn": "মাওলানা মোহাম্মদ ইসহাক",
        "ideology_summary_bn": "বাংলাদেশ খেলাফত মজলিস খিলাফত পুনঃপ্রতিষ্ঠার আদর্শে বিশ্বাসী একটি ইসলামপন্থী দল। দলটি কুরআন ও সুন্নাহ ভিত্তিক রাষ্ট্রব্যবস্থার দাবিতে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_15",
        "name_bn": "ইসলামী ঐক্যজোট",
        "name_en": "Islami Oikya Jot",
        "acronym": "IOJ",
        "founded_year": "1990",
        "current_head_bn": "আবদুল লতিফ নেজামী",
        "ideology_summary_bn": "ইসলামী ঐক্যজোট বিভিন্ন ইসলামপন্থী দলের সমন্বয়ে গঠিত একটি জোট। দলটি ইসলামি আইন ও মূল্যবোধ রক্ষার পক্ষে সোচ্চার এবং মুসলিম জাতীয়তাবাদী রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_16",
        "name_bn": "বাংলাদেশ তরিকত ফেডারেশন",
        "name_en": "Bangladesh Tarikat Federation",
        "acronym": "BTF",
        "founded_year": "2005",
        "current_head_bn": "নজিবুল বশর মাইজভান্ডারী",
        "ideology_summary_bn": "বাংলাদেশ তরিকত ফেডারেশন সুফি ও মাজারভিত্তিক ইসলামি ধারাকে প্রতিনিধিত্ব করে। দলটি পীর-মুরিদ সম্পর্কের ভিত্তিতে রাজনৈতিক সংগঠন পরিচালনা করে এবং ধর্মীয় সহিষ্ণুতায় বিশ্বাসী।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_17",
        "name_bn": "বাংলাদেশ মুসলিম লীগ",
        "name_en": "Bangladesh Muslim League",
        "acronym": "BML",
        "founded_year": "1906",
        "current_head_bn": "",
        "ideology_summary_bn": "ব্রিটিশ ভারতে মুসলমানদের জন্য আলাদা রাষ্ট্র প্রতিষ্ঠার আন্দোলনে নেতৃত্বদানকারী এই দল পাকিস্তান সৃষ্টির পর দুর্বল হয়ে পড়ে। বাংলাদেশে এর বেশ কয়েকটি অংশ ও উপদল বিদ্যমান।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_18",
        "name_bn": "গণতান্ত্রিক পার্টি",
        "name_en": "Democratic Party of Bangladesh",
        "acronym": "DP",
        "founded_year": "1952",
        "current_head_bn": "",
        "ideology_summary_bn": "বাংলাদেশের গণতান্ত্রিক পার্টি উদার গণতন্ত্রের আদর্শে পরিচালিত একটি ছোট কেন্দ্রপন্থী দল যা বহুদলীয় সংসদীয় গণতন্ত্রে বিশ্বাস করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_19",
        "name_bn": "বাংলাদেশ জাতীয় পার্টি (মঞ্জু)",
        "name_en": "Bangladesh Jatiya Party (Manju)",
        "acronym": "BJP-M",
        "founded_year": "1986",
        "current_head_bn": "আন্দালীব রহমান পার্থ",
        "ideology_summary_bn": "এরশাদের জাতীয় পার্টি থেকে বিভক্ত এই দল মধ্যপন্থী জাতীয়তাবাদী রাজনীতি অনুসরণ করে এবং তৃতীয় শক্তি হিসেবে নিজেকে প্রতিষ্ঠিত করার চেষ্টা করছে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_20",
        "name_bn": "বিকল্পধারা বাংলাদেশ",
        "name_en": "Bikalpadhara Bangladesh",
        "acronym": "BDB",
        "founded_year": "2004",
        "current_head_bn": "এ কিউ এম বদরুদ্দোজা চৌধুরী",
        "ideology_summary_bn": "বিকল্পধারা বাংলাদেশ একটি উদারনৈতিক গণতান্ত্রিক দল যা বিএনপি থেকে বের হয়ে গঠিত। দলটি দুর্নীতিমুক্ত প্রশাসন ও সুশাসনের দাবিতে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_21",
        "name_bn": "কৃষক শ্রমিক জনতা লীগ",
        "name_en": "Krishak Sramik Janata League",
        "acronym": "KSJL",
        "founded_year": "1999",
        "current_head_bn": "বাংলাদেশ",
        "ideology_summary_bn": "কৃষক শ্রমিক জনতা লীগ কৃষক ও শ্রমিক শ্রেণির অধিকার রক্ষায় কাজ করে। দলটি গ্রামীণ দরিদ্র ও প্রান্তিক জনগোষ্ঠীর স্বার্থে সামাজিক গণতান্ত্রিক আদর্শ অনুসরণ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_22",
        "name_bn": "জাতীয় পার্টি (জেপি-জাফর)",
        "name_en": "Jatiya Party (JP-Jafar)",
        "acronym": "JP-J",
        "founded_year": "2008",
        "current_head_bn": "মোস্তাফিজুর রহমান ফিজার",
        "ideology_summary_bn": "জাতীয় পার্টির আরেকটি উপদল যা জাফর ইমামের নেতৃত্বে বিভক্ত হয়েছে। মূল দলের মতোই কেন্দ্রপন্থী জাতীয়তাবাদী আদর্শ ধারণ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_23",
        "name_bn": "বাংলাদেশ ন্যাশনালিস্ট ফ্রন্ট",
        "name_en": "Bangladesh Nationalist Front",
        "acronym": "BNF",
        "founded_year": "1999",
        "current_head_bn": "এস. এম. আবুল কালাম আজাদ",
        "ideology_summary_bn": "বাংলাদেশ ন্যাশনালিস্ট ফ্রন্ট বিএনপির আদর্শ থেকে অনুপ্রাণিত একটি ছোট কেন্দ্র-ডানপন্থী দল যা বাংলাদেশি জাতীয়তাবাদের ভিত্তিতে রাজনীতি পরিচালনা করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_24",
        "name_bn": "বাংলাদেশ কল্যাণ পার্টি",
        "name_en": "Bangladesh Kalyan Party",
        "acronym": "BKP",
        "founded_year": "2007",
        "current_head_bn": "মেজর জেনারেল (অব.) সৈয়দ মুহাম্মদ ইবরাহিম",
        "ideology_summary_bn": "বাংলাদেশ কল্যাণ পার্টি একটি ইসলামিক গণতান্ত্রিক দল। দলটি নৈতিক ও আধ্যাত্মিক মূল্যবোধের ভিত্তিতে রাষ্ট্র পরিচালনা, সুশাসন ও দুর্নীতিমুক্ত প্রশাসনের দাবিতে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_25",
        "name_bn": "জাতীয় গণতান্ত্রিক পার্টি",
        "name_en": "Jatiya Ganatantrik Party",
        "acronym": "JGP",
        "founded_year": "1975",
        "current_head_bn": "শফিউল আলম প্রধান",
        "ideology_summary_bn": "জাতীয় গণতান্ত্রিক পার্টি একটি ডানপন্থী জাতীয়তাবাদী দল যা সংসদীয় গণতন্ত্র ও বাজার অর্থনীতির পক্ষে অবস্থান নেয়।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_26",
        "name_bn": "গণআজাদী লীগ",
        "name_en": "Gaon Azadi League",
        "acronym": "GAL",
        "founded_year": "1960",
        "current_head_bn": "",
        "ideology_summary_bn": "গণআজাদী লীগ বাংলাদেশের একটি বামপন্থী রাজনৈতিক দল যা জনগণের আজাদি ও শ্রেণিমুক্তির লক্ষ্যে কাজ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_27",
        "name_bn": "বাংলাদেশ সমাজতান্ত্রিক দল (বাসদ)",
        "name_en": "Bangladesh Socialist Party (BSD)",
        "acronym": "BSD",
        "founded_year": "1980",
        "current_head_bn": "খালেকুজ্জামান",
        "ideology_summary_bn": "বাংলাদেশ সমাজতান্ত্রিক দল মার্কসবাদী-লেনিনবাদী আদর্শে পরিচালিত। দলটি পুঁজিবাদের অবসান ঘটিয়ে একটি শ্রমিক-কৃষকের সমাজতান্ত্রিক সমাজ গড়ার লক্ষ্যে সংগ্রাম করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_28",
        "name_bn": "গণসংহতি আন্দোলন",
        "name_en": "Gano Sanghati Andolan",
        "acronym": "GSA",
        "founded_year": "2009",
        "current_head_bn": "জোনায়েদ সাকি",
        "ideology_summary_bn": "গণসংহতি আন্দোলন বাংলাদেশের একটি বামপন্থী রাজনৈতিক সংগঠন। এটি গণতান্ত্রিক অধিকার প্রতিষ্ঠা, সাম্রাজ্যবাদবিরোধিতা ও সমাজতান্ত্রিক পরিবর্তনের পক্ষে সোচ্চার।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_29",
        "name_bn": "গণ অধিকার পরিষদ",
        "name_en": "Gono Odhikar Parishad",
        "acronym": "GOP",
        "founded_year": "2022",
        "current_head_bn": "নুরুল হক নুর",
        "ideology_summary_bn": "গণ অধিকার পরিষদ ছাত্র আন্দোলন থেকে বের হয়ে আসা একটি তরুণ রাজনৈতিক দল। দলটি গণতান্ত্রিক সংস্কার, দুর্নীতিমুক্ত রাজনীতি এবং যুব নেতৃত্বের ভিত্তিতে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_30",
        "name_bn": "ন্যাশনাল পিপলস পার্টি (এনপিপি)",
        "name_en": "National People's Party",
        "acronym": "NPP",
        "founded_year": "1978",
        "current_head_bn": "শেখ শওকত হোসেন নিলু",
        "ideology_summary_bn": "ন্যাশনাল পিপলস পার্টি একটি কেন্দ্রপন্থী জাতীয়তাবাদী দল যা জনগণের অধিকার ও গণতন্ত্র প্রতিষ্ঠার পক্ষে কাজ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_31",
        "name_bn": "বাংলাদেশ লেবার পার্টি",
        "name_en": "Bangladesh Labour Party",
        "acronym": "BLP",
        "founded_year": "1982",
        "current_head_bn": "মোস্তাফিজুর রহমান ইবনে মোস্তফা",
        "ideology_summary_bn": "বাংলাদেশ লেবার পার্টি শ্রমজীবী মানুষের স্বার্থে কাজ করে এবং ট্রেড ইউনিয়নভিত্তিক রাজনীতি পরিচালনা করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_32",
        "name_bn": "পিপলস ডেমোক্রেটিক পার্টি (পিডিপি)",
        "name_en": "People's Democratic Party",
        "acronym": "PDP",
        "founded_year": "1976",
        "current_head_bn": "ফজলুর রহমান পটল",
        "ideology_summary_bn": "পিপলস ডেমোক্রেটিক পার্টি একটি গণতান্ত্রিক ও প্রগতিশীল দল যা সামাজিক ন্যায়বিচার ও জনগণের ক্ষমতায়নের পক্ষে কাজ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_33",
        "name_bn": "বাংলাদেশ ডেভেলপমেন্ট পার্টি (বিডিপি)",
        "name_en": "Bangladesh Development Party",
        "acronym": "BDP",
        "founded_year": "1978",
        "current_head_bn": "",
        "ideology_summary_bn": "বাংলাদেশ ডেভেলপমেন্ট পার্টি উন্নয়নমুখী রাজনীতির মাধ্যমে দেশের অর্থনৈতিক সমৃদ্ধি অর্জনের লক্ষ্যে কাজ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_34",
        "name_bn": "বাংলাদেশ খেলাফত আন্দোলন",
        "name_en": "Bangladesh Khelafat Andolon",
        "acronym": "BKA",
        "founded_year": "1981",
        "current_head_bn": "হাফেজ মাওলানা আতাউল্লাহ হাফেজী",
        "ideology_summary_bn": "বাংলাদেশ খেলাফত আন্দোলন একটি ইসলামপন্থী দল যা ইসলামি খিলাফত পুনঃপ্রতিষ্ঠা এবং কুরআন-সুন্নাহ ভিত্তিক সমাজ গঠনের লক্ষ্যে কাজ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_35",
        "name_bn": "বাংলাদেশ মুক্তিযোদ্ধা লীগ",
        "name_en": "Bangladesh Muktijoddha League",
        "acronym": "BML",
        "founded_year": "1972",
        "current_head_bn": "",
        "ideology_summary_bn": "বাংলাদেশ মুক্তিযোদ্ধা লীগ মুক্তিযোদ্ধাদের অধিকার সংরক্ষণ ও মুক্তিযুদ্ধের চেতনা বাস্তবায়নের লক্ষ্যে গঠিত একটি দল।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_36",
        "name_bn": "বাংলাদেশ জাতীয়তাবাদী সমাজতান্ত্রিক দল (বিএনএসপি)",
        "name_en": "Bangladesh Nationalistic Socialist Party",
        "acronym": "BNSP",
        "founded_year": "1983",
        "current_head_bn": "",
        "ideology_summary_bn": "বাংলাদেশ জাতীয়তাবাদী সমাজতান্ত্রিক দল জাতীয়তাবাদ ও সমাজতন্ত্রের মিশ্রণে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_37",
        "name_bn": "সাম্যবাদী দল",
        "name_en": "Samyabadi Dal",
        "acronym": "SD",
        "founded_year": "1967",
        "current_head_bn": "দিলীপ বড়ুয়া",
        "ideology_summary_bn": "সাম্যবাদী দল মার্কসবাদী আদর্শভিত্তিক একটি ছোট বামপন্থী দল যা শ্রমজীবী মানুষের অধিকার ও শ্রেণিমুক্তির পক্ষে কাজ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_38",
        "name_bn": "বাংলাদেশ মানবাধিকার পার্টি",
        "name_en": "Bangladesh Manabadhikar Party",
        "acronym": "BMP",
        "founded_year": "2005",
        "current_head_bn": "",
        "ideology_summary_bn": "বাংলাদেশ মানবাধিকার পার্টি সর্বজনীন মানবাধিকার প্রতিষ্ঠা, গণতন্ত্র সংরক্ষণ ও নাগরিক স্বাধীনতা নিশ্চিত করার লক্ষ্যে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_39",
        "name_bn": "বাংলাদেশ ইসলামি দল",
        "name_en": "Bangladesh Islami Dal",
        "acronym": "BID",
        "founded_year": "1979",
        "current_head_bn": "",
        "ideology_summary_bn": "বাংলাদেশ ইসলামি দল ইসলামি শাসনব্যবস্থা প্রতিষ্ঠা ও ইসলামি নৈতিকতার ভিত্তিতে সমাজ গড়ার পক্ষে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_40",
        "name_bn": "বাংলাদেশ জাতীয় লীগ",
        "name_en": "Bangladesh Jatiya League",
        "acronym": "BJL",
        "founded_year": "1968",
        "current_head_bn": "",
        "ideology_summary_bn": "বাংলাদেশ জাতীয় লীগ একটি পুরনো জাতীয়তাবাদী দল যা বাঙালি জাতিসত্তার বিকাশ ও সাংস্কৃতিক স্বাধীনতার পক্ষে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_41",
        "name_bn": "জাতীয় গণফ্রন্ট",
        "name_en": "Jatiya Gana Front",
        "acronym": "JGF",
        "founded_year": "1985",
        "current_head_bn": "নুরুল আমিন বাচ্চু",
        "ideology_summary_bn": "জাতীয় গণফ্রন্ট একটি বামপন্থী রাজনৈতিক সংগঠন যা গণতান্ত্রিক আন্দোলনে অংশগ্রহণ করে এবং জনগণের অধিকার প্রতিষ্ঠায় কাজ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_42",
        "name_bn": "প্রগতিশীল জাতীয়তাবাদী দল",
        "name_en": "Progressive Nationalist Party",
        "acronym": "PNP",
        "founded_year": "1975",
        "current_head_bn": "",
        "ideology_summary_bn": "প্রগতিশীল জাতীয়তাবাদী দল একটি মধ্যপন্থী দল যা বাংলাদেশি জাতীয়তাবাদ ও প্রগতিশীল সামাজিক মূল্যবোধকে একত্রিত করে রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_43",
        "name_bn": "বাংলাদেশ কংগ্রেস",
        "name_en": "Bangladesh Congress",
        "acronym": "BC",
        "founded_year": "2017",
        "current_head_bn": "একেএম মিজানুল হক",
        "ideology_summary_bn": "বাংলাদেশ কংগ্রেস একটি নতুন কেন্দ্রমুখী দল যা অন্তর্ভুক্তিমূলক রাজনীতি, সুশাসন ও সামাজিক উন্নয়নের পক্ষে কাজ করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_44",
        "name_bn": "গণতন্ত্রী পার্টি",
        "name_en": "Ganotantri Party",
        "acronym": "GP",
        "founded_year": "1983",
        "current_head_bn": "",
        "ideology_summary_bn": "গণতন্ত্রী পার্টি বাংলাদেশে সংসদীয় গণতন্ত্র ও আইনের শাসন প্রতিষ্ঠার পক্ষে কাজ করা একটি ছোট কেন্দ্রপন্থী দল।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_45",
        "name_bn": "জাতীয় পার্টি (নাজিউর)",
        "name_en": "Jatiya Party (Naziur)",
        "acronym": "JP-N",
        "founded_year": "2005",
        "current_head_bn": "নাজিউর রহমান মঞ্জু",
        "ideology_summary_bn": "জাতীয় পার্টির আরেকটি অংশ যা নাজিউর রহমান মঞ্জুর নেতৃত্বে পরিচালিত। মূল দলের মতো কেন্দ্রপন্থী জাতীয়তাবাদী রাজনীতি করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_46",
        "name_bn": "বাংলাদেশ পিপলস লীগ",
        "name_en": "Bangladesh Peoples League",
        "acronym": "BPL",
        "founded_year": "1994",
        "current_head_bn": "",
        "ideology_summary_bn": "বাংলাদেশ পিপলস লীগ একটি কেন্দ্রপন্থী দল যা জনগণের অধিকার ও গণতান্ত্রিক মূল্যবোধের ভিত্তিতে রাজনীতি পরিচালনা করে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_47",
        "name_bn": "জাতীয় নাগরিক পার্টি",
        "name_en": "National Citizen Party",
        "acronym": "NCP",
        "founded_year": "2025",
        "current_head_bn": "নাহিদ ইসলাম",
        "ideology_summary_bn": "জাতীয় নাগরিক পার্টি ২০২৪ সালের জুলাই-আগস্ট গণআন্দোলনের নেতাদের দ্বারা গঠিত একটি তরুণ রাজনৈতিক দল। দলটি গণতান্ত্রিক সংস্কার, দুর্নীতিমুক্ত রাষ্ট্র ও নতুন প্রজন্মের নেতৃত্বের প্রতিশ্রুতি নিয়ে কাজ করছে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
    {
        "entity_id": "pol_48",
        "name_bn": "বাংলাদেশ আইনজীবী পরিষদ",
        "name_en": "Bangladesh Ainjibi Parishad",
        "acronym": "BAP",
        "founded_year": "1980",
        "current_head_bn": "",
        "ideology_summary_bn": "আইনজীবীদের পেশাদার সংগঠন হিসেবে গঠিত হলেও এটি রাজনৈতিক কার্যক্রমে যুক্ত। দলটি সংবিধানের শাসন ও আইনের শাসন প্রতিষ্ঠার পক্ষে।",
        "wiki_image_url": "",
        "category": "Political Parties"
    },
]

FIELDS = ["entity_id", "name_bn", "name_en", "acronym", "founded_year", "current_head_bn", "ideology_summary_bn", "wiki_image_url", "category"]

outpath = os.path.join(DATA_DIR, "political_parties_enriched.csv")
with open(outpath, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(PARTIES)

print(f"Saved {len(PARTIES)} political parties to {outpath}")
