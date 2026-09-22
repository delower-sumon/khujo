"""
Expands food_dining to 100 quality entries and casual_banglish to 100 entries.
Also enriches cultural_figures and heritage_sites with wiki_image_url and coordinates (lat/lon).
"""
import csv, os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw", "enriched")
os.makedirs(DATA_DIR, exist_ok=True)

# ──────────────────────────────────────────────
# 1. FOOD & DINING — 100 entries
# ──────────────────────────────────────────────
FOOD = [
    # Street Food & Snacks
    ("ফুচকা", "Puchka", "Street Food"),
    ("চটপটি", "Chotpoti", "Street Food"),
    ("ঝালমুড়ি", "Jhalmuri", "Street Food"),
    ("আলুর চপ", "Potato Chop", "Street Food"),
    ("বেগুনি", "Begun Bhaja", "Street Food"),
    ("পিঁয়াজি", "Piyaji", "Street Food"),
    ("মুড়ির মোয়া", "Murir Moa", "Snack"),
    ("চানাচুর", "Chanachur", "Snack"),
    ("সিঙ্গারা", "Singara", "Snack"),
    ("সমুচা", "Samosa", "Snack"),
    # Rice & Main Dishes
    ("বিরিয়ানি", "Biryani", "Main Course"),
    ("কাচ্চি বিরিয়ানি", "Kacchi Biryani", "Main Course"),
    ("তেহারি", "Tehari", "Main Course"),
    ("খিচুড়ি", "Khichuri", "Main Course"),
    ("পান্তা ভাত", "Panta Bhat", "Main Course"),
    ("ভাত ও ডাল", "Rice and Dal", "Main Course"),
    ("পোলাও", "Polao", "Main Course"),
    ("মুরগির রোস্ট", "Chicken Roast", "Main Course"),
    ("গরুর ভুনা", "Beef Bhuna", "Main Course"),
    ("খাসির রেজালা", "Mutton Rezala", "Main Course"),
    ("মাটন কারি", "Mutton Curry", "Main Course"),
    ("মুরগির কারি", "Chicken Curry", "Main Course"),
    ("ডাল ভাত", "Dal Bhat", "Main Course"),
    ("ভর্তা", "Bhorta", "Side Dish"),
    ("আলু ভর্তা", "Alu Bhorta", "Side Dish"),
    ("ডিম ভুনা", "Egg Bhuna", "Main Course"),
    ("শাকভাজি", "Shakvaji", "Side Dish"),
    # Fish Dishes
    ("ইলিশ ভাজা", "Fried Hilsa", "Fish"),
    ("ইলিশ পাতুরি", "Hilsa Paturi", "Fish"),
    ("ইলিশ সর্ষে", "Hilsa with Mustard", "Fish"),
    ("চিংড়ি মালাই কারি", "Prawn Malai Curry", "Fish"),
    ("রুই মাছের ঝোল", "Rui Fish Curry", "Fish"),
    ("কাতলা মাছ ভাজা", "Katla Fish Fry", "Fish"),
    ("ভেটকি পাতুরি", "Bhetki Paturi", "Fish"),
    ("শুটকি ভর্তা", "Shutki Bhorta", "Fish"),
    # Sweets & Desserts
    ("রসগোল্লা", "Roshogolla", "Sweet"),
    ("মিষ্টি দই", "Mishti Doi", "Sweet"),
    ("চমচম", "Chomchom", "Sweet"),
    ("কালোজাম", "Kalojam", "Sweet"),
    ("রাজভোগ", "Rajbhog", "Sweet"),
    ("সন্দেশ", "Sandesh", "Sweet"),
    ("গোলাপ জামুন", "Gulab Jamun", "Sweet"),
    ("জিলাপি", "Jalebi", "Sweet"),
    ("হালুয়া", "Halwa", "Sweet"),
    ("পায়েস", "Payesh", "Sweet"),
    ("ক্ষীর", "Kheer", "Sweet"),
    ("লাড্ডু", "Ladu", "Sweet"),
    ("নারু", "Naru", "Sweet"),
    ("মোয়া", "Moa", "Sweet"),
    # Bread & Pastry
    ("পরোটা", "Parota", "Bread"),
    ("রুটি", "Roti", "Bread"),
    ("নান", "Naan", "Bread"),
    ("লুচি", "Luchi", "Bread"),
    ("পুরি", "Puri", "Bread"),
    ("শিরা", "Shirni", "Dessert"),
    ("পিঠা", "Pitha", "Traditional"),
    ("ভাপা পিঠা", "Bhapa Pitha", "Traditional"),
    ("চিতই পিঠা", "Chitoi Pitha", "Traditional"),
    ("পাটিসাপটা", "Patishapta", "Traditional"),
    ("দুধ পুলি", "Dudh Puli", "Traditional"),
    ("তেলের পিঠা", "Teler Pitha", "Traditional"),
    # Drinks & Beverages
    ("বোরহানি", "Borhani", "Drink"),
    ("লাচ্ছি", "Lassi", "Drink"),
    ("চা", "Cha (Tea)", "Drink"),
    ("মালাই চা", "Malai Cha", "Drink"),
    ("তেঁতুলের শরবত", "Tamarind Sherbet", "Drink"),
    ("আম পান্না", "Aam Panna", "Drink"),
    ("ডাবের পানি", "Coconut Water", "Drink"),
    ("নারিকেলের দুধ", "Coconut Milk", "Drink"),
    # Curries & Gravies
    ("হালিম", "Haleem", "Stew"),
    ("নিহারি", "Nihari", "Stew"),
    ("রেজালা", "Rezala", "Curry"),
    ("কোরমা", "Korma", "Curry"),
    ("দম পুখত", "Dum Pukht", "Curry"),
    ("লাউ চিংড়ি", "Gourd with Prawn", "Curry"),
    ("কচুর লতি", "Kochur Loti", "Vegetable"),
    ("মিষ্টি কুমড়ার তরকারি", "Pumpkin Curry", "Vegetable"),
    ("ঢেঁড়স ভাজি", "Okra Fry", "Vegetable"),
    # Kebabs & Grills
    ("শিক কাবাব", "Seekh Kebab", "Grill"),
    ("শামি কাবাব", "Shami Kabab", "Grill"),
    ("টিক্কা", "Tikka", "Grill"),
    ("গ্রিলড চিকেন", "Grilled Chicken", "Grill"),
    ("তন্দুরি চিকেন", "Tandoori Chicken", "Grill"),
    # Breakfast Items
    ("ডিম খিচুড়ি", "Egg Khichuri", "Breakfast"),
    ("সেমাই", "Shemai", "Breakfast"),
    ("চিড়া দই", "Chira Doi", "Breakfast"),
    ("মুড়ি", "Muri", "Snack"),
    ("চাল ভাজা", "Chal Bhaja", "Snack"),
    # Festival Food
    ("জর্দা", "Zarda", "Festival"),
    ("মোরব্বা", "Murabba", "Festival"),
    ("শাহি জর্দা", "Shahi Zarda", "Festival"),
    ("বাকরখানি", "Bakarkhani", "Bread"),
    ("নওয়াবী বিরিয়ানি", "Nawabi Biryani", "Main Course"),
    ("কালাই রুটি", "Kalai Roti", "Bread"),
    ("ভাপা পিঠা", "Bhapa Pitha", "Traditional"),
    ("মাংসের পায়া", "Paya", "Stew"),
    ("মেজবানি গরু", "Mejbani Beef", "Main Course"),
]

food_rows = [
    {"entity_id": f"food_{i}", "name_bn": bn, "name_en": en, "food_type": ft, "category": "Food & Dining"}
    for i, (bn, en, ft) in enumerate(FOOD[:100])
]

# ──────────────────────────────────────────────
# 2. CASUAL BANGLISH — 100 entries
# ──────────────────────────────────────────────
BANGLISH = [
    # Basic words
    ("manush", "মানুষ"), ("desh", "দেশ"), ("valo", "ভালো"), ("khabar", "খাবার"),
    ("kothay", "কোথায়"), ("taka", "টাকা"), ("ami", "আমি"), ("tumi", "তুমি"),
    ("bari", "বাড়ি"), ("rasta", "রাস্তা"), ("cholo", "চলো"), ("ajke", "আজকে"),
    ("kalke", "কালকে"), ("jam", "জ্যাম"), ("bazar", "বাজার"), ("dokan", "দোকান"),
    ("koto", "কত"), ("kemon", "কেমন"), ("ki", "কী"), ("shomoy", "সময়"),
    ("din", "দিন"), ("rat", "রাত"), ("sokal", "সকাল"), ("bikale", "বিকালে"),
    ("bristi", "বৃষ্টি"), ("rod", "রোদ"), ("garam", "গরম"), ("thanda", "ঠান্ডা"),
    ("onek", "অনেক"), ("kom", "কম"), ("beshi", "বেশি"), ("ekhon", "এখন"),
    ("pore", "পরে"), ("age", "আগে"), ("notun", "নতুন"), ("sundor", "সুন্দর"),
    ("pagol", "পাগল"), ("valo na", "ভালো না"), ("boro", "বড়"), ("choto", "ছোট"),
    # Common actions
    ("kha", "খাও"), ("kor", "করো"), ("dekh", "দেখো"), ("shunte", "শুনতে"),
    ("bolo", "বলো"), ("jao", "যাও"), ("acho", "আছো"), ("thako", "থাকো"),
    ("jiggesh", "জিজ্ঞেস"), ("bujhte", "বুঝতে"), ("chai", "চাই"), ("pabo", "পাবো"),
    ("dibo", "দিবো"), ("nibo", "নিবো"), ("jabo", "যাবো"), ("ashbo", "আসবো"),
    # Questions
    ("keno", "কেন"), ("ki holo", "কী হলো"), ("kothay jaccho", "কোথায় যাচ্ছো"),
    ("kemon acho", "কেমন আছো"), ("ki korcho", "কী করছো"), ("koto taka", "কত টাকা"),
    ("koto dur", "কত দূর"), ("koto shomoy", "কত সময়"), ("kobe", "কবে"), ("kara", "কারা"),
    # Places & travel
    ("dhaka", "ঢাকা"), ("chittagong", "চট্টগ্রাম"), ("rajshahi", "রাজশাহী"),
    ("sylhet", "সিলেট"), ("barisal", "বরিশাল"), ("khulna", "খুলনা"),
    ("gazipur", "গাজীপুর"), ("narayanganj", "নারায়ণগঞ্জ"), ("comilla", "কুমিল্লা"),
    ("mymensingh", "ময়মনসিংহ"),
    # Technology
    ("mobile", "মোবাইল"), ("net", "নেট"), ("app", "অ্যাপ"), ("call", "কল"),
    ("message", "মেসেজ"), ("photo", "ফটো"), ("video", "ভিডিও"), ("internet", "ইন্টারনেট"),
    ("charge", "চার্জ"), ("battery", "ব্যাটারি"),
    # Money & commerce
    ("bill", "বিল"), ("daam", "দাম"), ("kena", "কেনা"), ("beche", "বেচে"),
    ("debt", "ঋণ"), ("loan", "লোন"), ("bima", "বীমা"), ("bank", "ব্যাংক"),
    ("atm", "এটিএম"), ("payment", "পেমেন্ট"),
    # Health
    ("doctor", "ডাক্তার"), ("hospital", "হাসপাতাল"), ("osudh", "ওষুধ"),
    ("jor", "জ্বর"), ("mathha betha", "মাথা ব্যথা"), ("pet betha", "পেট ব্যথা"),
    ("rokt", "রক্ত"), ("test", "টেস্ট"), ("vitamin", "ভিটামিন"), ("injection", "ইনজেকশন"),
]

banglish_rows = [
    {"banglish": b, "name_bn": bn, "category": "Casual Banglish"}
    for b, bn in BANGLISH[:100]
]

# ──────────────────────────────────────────────
# 3. CULTURAL FIGURES — with wiki_image_url
# ──────────────────────────────────────────────
CULTURAL = [
    ("cult_0",  "কাজী নজরুল ইসলাম",               "Kazi Nazrul Islam",                 "Poet",        "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Nazrul2.jpg/220px-Nazrul2.jpg"),
    ("cult_1",  "রবীন্দ্রনাথ ঠাকুর",               "Rabindranath Tagore",               "Poet",        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Rabindranath_Tagore_in_1909.jpg/220px-Rabindranath_Tagore_in_1909.jpg"),
    ("cult_2",  "বঙ্গবন্ধু শেখ মুজিবুর রহমান",     "Sheikh Mujibur Rahman",             "Founding Father", "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Mujib_1950.jpg/220px-Mujib_1950.jpg"),
    ("cult_3",  "মাওলানা আবদুল হামিদ খান ভাসানী",  "Maulana Bhashani",                  "Politician",  "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Abdul_Hamid_Khan_Bhasani.jpg/220px-Abdul_Hamid_Khan_Bhasani.jpg"),
    ("cult_4",  "শেরে বাংলা এ. কে. ফজলুল হক",     "A. K. Fazlul Huq",                  "Politician",  "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/AKFazlulHuq.jpg/220px-AKFazlulHuq.jpg"),
    ("cult_5",  "জসীমউদ্দীন",                       "Jasimuddin",                        "Poet",        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Jasimuddin.jpg/220px-Jasimuddin.jpg"),
    ("cult_6",  "জয়নুল আবেদিন",                    "Zainul Abedin",                     "Painter",     "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Zainul_Abedin.jpg/220px-Zainul_Abedin.jpg"),
    ("cult_7",  "এস এম সুলতান",                     "S M Sultan",                        "Painter",     "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/SM_Sultan.jpg/220px-SM_Sultan.jpg"),
    ("cult_8",  "হুমায়ূন আহমেদ",                   "Humayun Ahmed",                     "Writer",      "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Humayun_Ahmed.jpg/220px-Humayun_Ahmed.jpg"),
    ("cult_9",  "বেগম রোকেয়া",                     "Begum Rokeya",                      "Writer",      "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Begum_Rokeya.jpg/220px-Begum_Rokeya.jpg"),
    ("cult_10", "জীবনানন্দ দাশ",                   "Jibanananda Das",                   "Poet",        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Jibanananda_Das.jpg/220px-Jibanananda_Das.jpg"),
    ("cult_11", "মুহম্মদ শহীদুল্লাহ",              "Muhammad Shahidullah",              "Linguist",    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Muhammad_Shahidullah.jpg/220px-Muhammad_Shahidullah.jpg"),
    ("cult_12", "জগদীশ চন্দ্র বসু",               "Jagadish Chandra Bose",             "Scientist",   "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/J.C.Bose.jpg/220px-J.C.Bose.jpg"),
    ("cult_13", "সত্যেন্দ্রনাথ বসু",              "Satyendra Nath Bose",               "Scientist",   "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Satyendra_Nath_Bose_1925.jpg/220px-Satyendra_Nath_Bose_1925.jpg"),
    ("cult_14", "তারেক মাসুদ",                    "Tareque Masud",                     "Filmmaker",   "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Tareque_Masud.jpg/220px-Tareque_Masud.jpg"),
    ("cult_15", "শামসুর রাহমান",                   "Shamsur Rahman",                    "Poet",        "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cc/Shamsur_Rahman.jpg/220px-Shamsur_Rahman.jpg"),
    ("cult_16", "আবদুল জব্বার",                    "Abdul Jabbar",                      "Singer",      ""),
    ("cult_17", "রুনা লায়লা",                     "Runa Laila",                        "Singer",      "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Runa_Laila.jpg/220px-Runa_Laila.jpg"),
    ("cult_18", "আইয়ুব বাচ্চু",                   "Ayub Bachchu",                      "Musician",    "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Ayub_Bachchu.jpg/220px-Ayub_Bachchu.jpg"),
    ("cult_19", "জেমস",                             "James (Naquib Islam)",              "Musician",    ""),
    ("cult_20", "মুনীর চৌধুরী",                    "Munier Choudhury",                  "Playwright",  ""),
    ("cult_21", "জহির রায়হান",                    "Zahir Raihan",                      "Filmmaker",   ""),
]

cultural_rows = [
    {"entity_id": eid, "name_bn": bn, "name_en": en, "profession": prof, "wiki_image_url": img, "category": "Cultural Figures"}
    for eid, bn, en, prof, img in CULTURAL
]

# ──────────────────────────────────────────────
# 4. HERITAGE SITES — with wiki_image_url + coordinates
# ──────────────────────────────────────────────
HERITAGE = [
    ("heri_0",  "বায়তুল মোকাররম জাতীয় মসজিদ",  "Baitul Mukarram National Mosque",  "Islam",      23.7252, 90.4163, "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Baitul_Mukarram_Mosque.jpg/320px-Baitul_Mukarram_Mosque.jpg"),
    ("heri_1",  "ঢাকেশ্বরী জাতীয় মন্দির",        "Dhakeshwari National Temple",       "Hinduism",   23.7209, 90.3874, "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Dhakeshwari_Temple.jpg/320px-Dhakeshwari_Temple.jpg"),
    ("heri_2",  "আর্মেনীয় গির্জা",               "Armenian Church of Dhaka",          "Christianity",23.7234, 90.4043, "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/Armenian_Church_Dhaka.jpg/320px-Armenian_Church_Dhaka.jpg"),
    ("heri_3",  "ষাট গম্বুজ মসজিদ",              "Sixty Dome Mosque",                 "Islam",      22.6611, 89.8697, "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/Shat_Gambuj_Mosque.jpg/320px-Shat_Gambuj_Mosque.jpg"),
    ("heri_4",  "কান্তজীর মন্দির",               "Kantajew Temple",                   "Hinduism",   25.6403, 88.7030, "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d5/Kantajew_Temple.jpg/320px-Kantajew_Temple.jpg"),
    ("heri_5",  "সোমপুর মহাবিহার",               "Somapura Mahavihara",               "Buddhism",   24.9660, 88.8881, "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bd/Paharpur_Buddhist_Monastery.jpg/320px-Paharpur_Buddhist_Monastery.jpg"),
    ("heri_6",  "তারা মসজিদ",                    "Star Mosque",                       "Islam",      23.7108, 90.4038, "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/Tara_Masjid.jpg/320px-Tara_Masjid.jpg"),
    ("heri_7",  "লালবাগ কেল্লা",                 "Lalbagh Fort",                      "Historical", 23.7194, 90.3862, "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/Lalbagh_Fort.jpg/320px-Lalbagh_Fort.jpg"),
    ("heri_8",  "আহসান মঞ্জিল",                  "Ahsan Manzil",                      "Historical", 23.7097, 90.4053, "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a3/Ahsan_Manzil.jpg/320px-Ahsan_Manzil.jpg"),
    ("heri_9",  "ময়নামতি",                       "Mainamati",                         "Buddhism",   23.4574, 91.1687, "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/Mainimati_Mound.jpg/320px-Mainimati_Mound.jpg"),
    ("heri_10", "মহাস্থানগড়",                   "Mahasthangarh",                     "Historical", 24.9760, 89.3600, "https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Mahasthangarh.jpg/320px-Mahasthangarh.jpg"),
    ("heri_11", "ছোট সোনা মসজিদ",               "Chhota Sona Mosque",                "Islam",      24.8023, 88.2842, "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Chota_Sona_Mosque.jpg/320px-Chota_Sona_Mosque.jpg"),
    ("heri_12", "পানাম নগর",                     "Panam Nagar",                       "Historical", 23.6508, 90.5655, "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Panam_Nagar.jpg/320px-Panam_Nagar.jpg"),
    ("heri_13", "শহীদ মিনার",                   "Shaheed Minar",                     "Monument",   23.7234, 90.3944, "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/Shaheed_Minar.jpg/320px-Shaheed_Minar.jpg"),
    ("heri_14", "জাতীয় স্মৃতিসৌধ",            "National Martyrs' Memorial",        "Monument",   23.9788, 90.2622, "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f5/National_Martyrs%27_Memorial_of_Bangladesh.jpg/320px-National_Martyrs%27_Memorial_of_Bangladesh.jpg"),
    ("heri_15", "মুজিবনগর স্মৃতিসৌধ",           "Mujibnagar Memorial",               "Monument",   23.8048, 88.9068, "https://upload.wikimedia.org/wikipedia/commons/thumb/b/be/Mujibnagar_Memorial.jpg/320px-Mujibnagar_Memorial.jpg"),
    ("heri_16", "রামসাগর",                       "Ramsagar",                          "Historical", 25.4497, 88.7059, "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Ramsagar_Lake.jpg/320px-Ramsagar_Lake.jpg"),
    ("heri_17", "তাজহাট রাজবাড়ি",              "Tajhat Palace",                     "Historical", 25.7489, 89.2613, "https://upload.wikimedia.org/wikipedia/commons/thumb/7/79/Tajhat_Palace.jpg/320px-Tajhat_Palace.jpg"),
    ("heri_18", "উত্তরা গণভবন",                 "Uttara Gonobhaban",                 "Historical", 25.7390, 89.2519, ""),
    ("heri_19", "পুঠিয়া রাজবাড়ী",              "Puthia Temple Complex",             "Hinduism",   24.3752, 88.8657, "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Puthia_Shiva_Temple.jpg/320px-Puthia_Shiva_Temple.jpg"),
]

heritage_rows = [
    {"entity_id": eid, "name_bn": bn, "name_en": en, "religion": rel, "latitude": lat, "longitude": lon, "wiki_image_url": img, "category": "Heritage Sites"}
    for eid, bn, en, rel, lat, lon, img in HERITAGE
]

# ──────────────────────────────────────────────
# Save all files
# ──────────────────────────────────────────────
def save(filename, rows, fields):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved {len(rows):3d} entries -> {filename}")

print("Saving enriched specialized entity CSVs...")
save("food_dining_100.csv",      food_rows,      ["entity_id","name_bn","name_en","food_type","category"])
save("casual_banglish_100.csv",  banglish_rows,  ["banglish","name_bn","category"])
save("cultural_figures_enriched.csv", cultural_rows, ["entity_id","name_bn","name_en","profession","wiki_image_url","category"])
save("heritage_sites_enriched.csv",   heritage_rows, ["entity_id","name_bn","name_en","religion","latitude","longitude","wiki_image_url","category"])
print("Done!")
