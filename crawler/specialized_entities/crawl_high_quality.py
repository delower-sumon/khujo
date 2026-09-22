import os
import csv

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")
os.makedirs(DATA_DIR, exist_ok=True)

def save_csv(filename, data, fieldnames):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Saved {len(data)} entries to {filepath}")

# 1. Universities
universities = [
    {"entity_id": "uni_01", "name_bn": "ঢাকা বিশ্ববিদ্যালয়", "name_en": "Dhaka University", "acronym": "DU", "category": "Universities"},
    {"entity_id": "uni_02", "name_bn": "জাহাঙ্গীরনগর বিশ্ববিদ্যালয়", "name_en": "Jahangirnagar University", "acronym": "JU", "category": "Universities"},
    {"entity_id": "uni_03", "name_bn": "রাজশাহী বিশ্ববিদ্যালয়", "name_en": "Rajshahi University", "acronym": "RU", "category": "Universities"},
    {"entity_id": "uni_04", "name_bn": "বাংলাদেশ প্রকৌশল বিশ্ববিদ্যালয়", "name_en": "Bangladesh University of Engineering and Technology", "acronym": "BUET", "category": "Universities"},
    {"entity_id": "uni_05", "name_bn": "চট্টগ্রাম বিশ্ববিদ্যালয়", "name_en": "Chittagong University", "acronym": "CU", "category": "Universities"},
    {"entity_id": "uni_06", "name_bn": "জগন্নাথ বিশ্ববিদ্যালয়", "name_en": "Jagannath University", "acronym": "JNU", "category": "Universities"},
    {"entity_id": "uni_07", "name_bn": "খুলনা বিশ্ববিদ্যালয়", "name_en": "Khulna University", "acronym": "KU", "category": "Universities"},
    {"entity_id": "uni_08", "name_bn": "বরিশাল বিশ্ববিদ্যালয়", "name_en": "Barisal University", "acronym": "BU", "category": "Universities"},
    {"entity_id": "uni_09", "name_bn": "কুমিল্লা বিশ্ববিদ্যালয়", "name_en": "Comilla University", "acronym": "COU", "category": "Universities"},
    {"entity_id": "uni_10", "name_bn": "জাতীয় বিশ্ববিদ্যালয়", "name_en": "National University", "acronym": "NU", "category": "Universities"},
    {"entity_id": "uni_11", "name_bn": "শাহজালাল বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয়", "name_en": "Shahjalal University of Science and Technology", "acronym": "SUST", "category": "Universities"},
    {"entity_id": "uni_12", "name_bn": "ইসলামী বিশ্ববিদ্যালয়", "name_en": "Islamic University", "acronym": "IU", "category": "Universities"},
    {"entity_id": "uni_13", "name_bn": "বেগম রোকেয়া বিশ্ববিদ্যালয়", "name_en": "Begum Rokeya University", "acronym": "BRUR", "category": "Universities"},
    {"entity_id": "uni_14", "name_bn": "মাওলানা ভাসানী বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয়", "name_en": "Mawlana Bhashani Science and Technology University", "acronym": "MBSTU", "category": "Universities"},
    {"entity_id": "uni_15", "name_bn": "নোয়াখালী বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয়", "name_en": "Noakhali Science and Technology University", "acronym": "NSTU", "category": "Universities"},
    {"entity_id": "uni_16", "name_bn": "হাজী মোহাম্মদ দানেশ বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয়", "name_en": "Hajee Mohammad Danesh Science and Technology University", "acronym": "HSTU", "category": "Universities"},
    {"entity_id": "uni_17", "name_bn": "বঙ্গবন্ধু শেখ মুজিবুর রহমান কৃষি বিশ্ববিদ্যালয়", "name_en": "Bangabandhu Sheikh Mujibur Rahman Agricultural University", "acronym": "BSMRAU", "category": "Universities"},
    {"entity_id": "uni_18", "name_bn": "শেরেবাংলা কৃষি বিশ্ববিদ্যালয়", "name_en": "Sher-e-Bangla Agricultural University", "acronym": "SAU", "category": "Universities"},
    {"entity_id": "uni_19", "name_bn": "সিলেট কৃষি বিশ্ববিদ্যালয়", "name_en": "Sylhet Agricultural University", "acronym": "SAU", "category": "Universities"},
    {"entity_id": "uni_20", "name_bn": "যশোর বিজ্ঞান ও প্রযুক্তি বিশ্ববিদ্যালয়", "name_en": "Jessore University of Science and Technology", "acronym": "JUST", "category": "Universities"},
]

# 2. Political Parties
political_parties = [
    {"entity_id": "pol_01", "name_bn": "বাংলাদেশ আওয়ামী লীগ", "name_en": "Bangladesh Awami League", "acronym": "AL", "category": "Political Parties"},
    {"entity_id": "pol_02", "name_bn": "বাংলাদেশ জাতীয়তাবাদী দল", "name_en": "Bangladesh Nationalist Party", "acronym": "BNP", "category": "Political Parties"},
    {"entity_id": "pol_03", "name_bn": "জাতীয় পার্টি", "name_en": "Jatiya Party", "acronym": "JP", "category": "Political Parties"},
    {"entity_id": "pol_04", "name_bn": "বাংলাদেশ জামায়াতে ইসলামী", "name_en": "Bangladesh Jamaat-e-Islami", "acronym": "BJI", "category": "Political Parties"},
    {"entity_id": "pol_05", "name_bn": "বাংলাদেশের কমিউনিস্ট পার্টি", "name_en": "Communist Party of Bangladesh", "acronym": "CPB", "category": "Political Parties"},
    {"entity_id": "pol_06", "name_bn": "জাতীয় সমাজতান্ত্রিক দল", "name_en": "Jatiya Samajtantrik Dal", "acronym": "JSD", "category": "Political Parties"},
    {"entity_id": "pol_07", "name_bn": "বাংলাদেশের ওয়ার্কার্স পার্টি", "name_en": "Workers Party of Bangladesh", "acronym": "WPB", "category": "Political Parties"},
    {"entity_id": "pol_08", "name_bn": "ইসলামী আন্দোলন বাংলাদেশ", "name_en": "Islami Andolan Bangladesh", "acronym": "IAB", "category": "Political Parties"},
    {"entity_id": "pol_09", "name_bn": "লিবারেল ডেমোক্রেটিক পার্টি", "name_en": "Liberal Democratic Party", "acronym": "LDP", "category": "Political Parties"},
    {"entity_id": "pol_10", "name_bn": "গণফোরাম", "name_en": "Gano Forum", "acronym": "GF", "category": "Political Parties"},
]

# 3. Food
food = [
    {"entity_id": "food_01", "name_bn": "ফুচকা", "name_en": "Puchka", "category": "Food & Dining"},
    {"entity_id": "food_02", "name_bn": "বিরিয়ানি", "name_en": "Biryani", "category": "Food & Dining"},
    {"entity_id": "food_03", "name_bn": "কাচ্চি বিরিয়ানি", "name_en": "Kacchi Biryani", "category": "Food & Dining"},
    {"entity_id": "food_04", "name_bn": "তেহারি", "name_en": "Tehari", "category": "Food & Dining"},
    {"entity_id": "food_05", "name_bn": "চটপটি", "name_en": "Chotpoti", "category": "Food & Dining"},
    {"entity_id": "food_06", "name_bn": "রসগোল্লা", "name_en": "Roshogolla", "category": "Food & Dining"},
    {"entity_id": "food_07", "name_bn": "মিষ্টি দই", "name_en": "Mishti Doi", "category": "Food & Dining"},
    {"entity_id": "food_08", "name_bn": "ভর্তা", "name_en": "Bhorta", "category": "Food & Dining"},
    {"entity_id": "food_09", "name_bn": "ইলিশ ভাজা", "name_en": "Fried Hilsa", "category": "Food & Dining"},
    {"entity_id": "food_10", "name_bn": "পান্তা ভাত", "name_en": "Panta Bhat", "category": "Food & Dining"},
    {"entity_id": "food_11", "name_bn": "হালিম", "name_en": "Haleem", "category": "Food & Dining"},
    {"entity_id": "food_12", "name_bn": "বোরহানি", "name_en": "Borhani", "category": "Food & Dining"},
    {"entity_id": "food_13", "name_bn": "ঝালমুড়ি", "name_en": "Jhalmuri", "category": "Food & Dining"},
    {"entity_id": "food_14", "name_bn": "সমুচা", "name_en": "Samosa", "category": "Food & Dining"},
    {"entity_id": "food_15", "name_bn": "সিঙ্গারা", "name_en": "Singara", "category": "Food & Dining"},
    {"entity_id": "food_16", "name_bn": "জিলাপি", "name_en": "Jalebi", "category": "Food & Dining"},
]

# 4. Public Figures
public_figures = [
    {"entity_id": "fig_01", "name_bn": "প্রধানমন্ত্রী", "name_en": "Prime Minister", "acronym": "PM", "category": "Public Figures"},
    {"entity_id": "fig_02", "name_bn": "রাষ্ট্রপতি", "name_en": "President", "acronym": "", "category": "Public Figures"},
    {"entity_id": "fig_03", "name_bn": "শিক্ষামন্ত্রী", "name_en": "Education Minister", "acronym": "", "category": "Public Figures"},
    {"entity_id": "fig_04", "name_bn": "স্বরাষ্ট্রমন্ত্রী", "name_en": "Home Minister", "acronym": "", "category": "Public Figures"},
    {"entity_id": "fig_05", "name_bn": "মেয়র", "name_en": "Mayor", "acronym": "", "category": "Public Figures"},
    {"entity_id": "fig_06", "name_bn": "প্রধান বিচারপতি", "name_en": "Chief Justice", "acronym": "CJ", "category": "Public Figures"},
    {"entity_id": "fig_07", "name_bn": "সেনাপ্রধান", "name_en": "Army Chief", "acronym": "", "category": "Public Figures"},
    {"entity_id": "fig_08", "name_bn": "আইজিপি", "name_en": "Inspector General of Police", "acronym": "IGP", "category": "Public Figures"},
    {"entity_id": "fig_09", "name_bn": "অর্থমন্ত্রী", "name_en": "Finance Minister", "acronym": "", "category": "Public Figures"},
    {"entity_id": "fig_10", "name_bn": "পররাষ্ট্রমন্ত্রী", "name_en": "Foreign Minister", "acronym": "", "category": "Public Figures"},
]

# 5. Common Services
common_services = [
    {"entity_id": "srv_01", "name_bn": "হাসপাতাল", "name_en": "Hospital", "acronym": "", "category": "Common Services"},
    {"entity_id": "srv_02", "name_bn": "থানা", "name_en": "Police Station", "acronym": "PS", "category": "Common Services"},
    {"entity_id": "srv_03", "name_bn": "ফায়ার সার্ভিস", "name_en": "Fire Service", "acronym": "", "category": "Common Services"},
    {"entity_id": "srv_04", "name_bn": "রেলওয়ে স্টেশন", "name_en": "Railway Station", "acronym": "", "category": "Common Services"},
    {"entity_id": "srv_05", "name_bn": "বিমানবন্দর", "name_en": "Airport", "acronym": "", "category": "Common Services"},
    {"entity_id": "srv_06", "name_bn": "পোস্ট অফিস", "name_en": "Post Office", "acronym": "", "category": "Common Services"},
    {"entity_id": "srv_07", "name_bn": "ব্যাংক", "name_en": "Bank", "acronym": "", "category": "Common Services"},
    {"entity_id": "srv_08", "name_bn": "এটিএম", "name_en": "ATM", "acronym": "ATM", "category": "Common Services"},
    {"entity_id": "srv_09", "name_bn": "ফার্মেসি", "name_en": "Pharmacy", "acronym": "", "category": "Common Services"},
    {"entity_id": "srv_10", "name_bn": "রেস্তোরাঁ", "name_en": "Restaurant", "acronym": "", "category": "Common Services"},
]

# 6. Casual Banglish (Mapping banglish to bangla directly)
casual_banglish = [
    {"banglish": "manush", "name_bn": "মানুষ", "category": "Casual Banglish"},
    {"banglish": "desh", "name_bn": "দেশ", "category": "Casual Banglish"},
    {"banglish": "valo", "name_bn": "ভালো", "category": "Casual Banglish"},
    {"banglish": "khabar", "name_bn": "খাবার", "category": "Casual Banglish"},
    {"banglish": "kothay", "name_bn": "কোথায়", "category": "Casual Banglish"},
    {"banglish": "taka", "name_bn": "টাকা", "category": "Casual Banglish"},
    {"banglish": "ami", "name_bn": "আমি", "category": "Casual Banglish"},
    {"banglish": "tumi", "name_bn": "তুমি", "category": "Casual Banglish"},
    {"banglish": "bari", "name_bn": "বাড়ি", "category": "Casual Banglish"},
    {"banglish": "rasta", "name_bn": "রাস্তা", "category": "Casual Banglish"},
    {"banglish": "cholo", "name_bn": "চলো", "category": "Casual Banglish"},
    {"banglish": "ajke", "name_bn": "আজকে", "category": "Casual Banglish"},
    {"banglish": "kalke", "name_bn": "কালকে", "category": "Casual Banglish"},
    {"banglish": "jam", "name_bn": "জ্যাম", "category": "Casual Banglish"},
    {"banglish": "bazar", "name_bn": "বাজার", "category": "Casual Banglish"},
    {"banglish": "dokar", "name_bn": "দোকান", "category": "Casual Banglish"},
    {"banglish": "dokan", "name_bn": "দোকান", "category": "Casual Banglish"},
    {"banglish": "koto", "name_bn": "কত", "category": "Casual Banglish"},
    {"banglish": "kemon", "name_bn": "কেমন", "category": "Casual Banglish"},
    {"banglish": "ki", "name_bn": "কী", "category": "Casual Banglish"},
]

# 7. Cultural Figures
cultural_figures = [
    {"entity_id": "cult_01", "name_bn": "কাজী নজরুল ইসলাম", "name_en": "Kazi Nazrul Islam", "profession": "Poet", "category": "Cultural Figures"},
    {"entity_id": "cult_02", "name_bn": "রবীন্দ্রনাথ ঠাকুর", "name_en": "Rabindranath Tagore", "profession": "Poet", "category": "Cultural Figures"},
    {"entity_id": "cult_03", "name_bn": "বঙ্গবন্ধু শেখ মুজিবুর রহমান", "name_en": "Bangabandhu Sheikh Mujibur Rahman", "profession": "Founding Father", "category": "Cultural Figures"},
    {"entity_id": "cult_04", "name_bn": "মাওলানা আবদুল হামিদ খান ভাসানী", "name_en": "Maulana Abdul Hamid Khan Bhashani", "profession": "Politician", "category": "Cultural Figures"},
    {"entity_id": "cult_05", "name_bn": "শেরে বাংলা এ. কে. ফজলুল হক", "name_en": "A. K. Fazlul Huq", "profession": "Politician", "category": "Cultural Figures"},
    {"entity_id": "cult_06", "name_bn": "জসীমউদ্দীন", "name_en": "Jasimuddin", "profession": "Poet", "category": "Cultural Figures"},
    {"entity_id": "cult_07", "name_bn": "জয়নুল আবেদিন", "name_en": "Zainul Abedin", "profession": "Painter", "category": "Cultural Figures"},
    {"entity_id": "cult_08", "name_bn": "এস এম সুলতান", "name_en": "S M Sultan", "profession": "Painter", "category": "Cultural Figures"},
    {"entity_id": "cult_09", "name_bn": "হুমায়ূন আহমেদ", "name_en": "Humayun Ahmed", "profession": "Writer", "category": "Cultural Figures"},
    {"entity_id": "cult_10", "name_bn": "বেগম রোকেয়া", "name_en": "Begum Rokeya", "profession": "Writer", "category": "Cultural Figures"},
    {"entity_id": "cult_11", "name_bn": "জীবনানন্দ দাশ", "name_en": "Jibanananda Das", "profession": "Poet", "category": "Cultural Figures"},
    {"entity_id": "cult_12", "name_bn": "মুহম্মদ শহীদুল্লাহ", "name_en": "Muhammad Shahidullah", "profession": "Linguist", "category": "Cultural Figures"},
    {"entity_id": "cult_13", "name_bn": "জগদীশ চন্দ্র বসু", "name_en": "Jagadish Chandra Bose", "profession": "Scientist", "category": "Cultural Figures"},
    {"entity_id": "cult_14", "name_bn": "সত্যেন্দ্রনাথ বসু", "name_en": "Satyendra Nath Bose", "profession": "Scientist", "category": "Cultural Figures"},
    {"entity_id": "cult_15", "name_bn": "তারেক মাসুদ", "name_en": "Tareque Masud", "profession": "Filmmaker", "category": "Cultural Figures"},
]

# 8. Heritage Sites
heritage_sites = [
    {"entity_id": "heri_01", "name_bn": "বায়তুল মোকাররম জাতীয় মসজিদ", "name_en": "Baitul Mukarram National Mosque", "religion": "Islam", "category": "Heritage Sites"},
    {"entity_id": "heri_02", "name_bn": "ঢাকেশ্বরী জাতীয় মন্দির", "name_en": "Dhakeshwari National Temple", "religion": "Hinduism", "category": "Heritage Sites"},
    {"entity_id": "heri_03", "name_bn": "আর্মেনীয় গির্জা", "name_en": "Armenian Church", "religion": "Christianity", "category": "Heritage Sites"},
    {"entity_id": "heri_04", "name_bn": "ষাট গম্বুজ মসজিদ", "name_en": "Sixty Dome Mosque", "religion": "Islam", "category": "Heritage Sites"},
    {"entity_id": "heri_05", "name_bn": "কান্তজীর মন্দির", "name_en": "Kantajew Temple", "religion": "Hinduism", "category": "Heritage Sites"},
    {"entity_id": "heri_06", "name_bn": "সোমপুর মহাবিহার", "name_en": "Somapura Mahavihara", "religion": "Buddhism", "category": "Heritage Sites"},
    {"entity_id": "heri_07", "name_bn": "তারা মসজিদ", "name_en": "Star Mosque", "religion": "Islam", "category": "Heritage Sites"},
    {"entity_id": "heri_08", "name_bn": "লালবাগ কেল্লা", "name_en": "Lalbagh Fort", "religion": "Historical", "category": "Heritage Sites"},
    {"entity_id": "heri_09", "name_bn": "আহসান মঞ্জিল", "name_en": "Ahsan Manzil", "religion": "Historical", "category": "Heritage Sites"},
    {"entity_id": "heri_10", "name_bn": "ময়নামতি", "name_en": "Mainamati", "religion": "Buddhism", "category": "Heritage Sites"},
    {"entity_id": "heri_11", "name_bn": "মহাস্থানগড়", "name_en": "Mahasthangarh", "religion": "Historical", "category": "Heritage Sites"},
    {"entity_id": "heri_12", "name_bn": "ছোট সোনা মসজিদ", "name_en": "Chhota Sona Mosque", "religion": "Islam", "category": "Heritage Sites"},
]

def main():
    print(f"Saving high-quality data to: {DATA_DIR}")
    save_csv("universities.csv", universities, ["entity_id", "name_bn", "name_en", "acronym", "category"])
    save_csv("political_parties.csv", political_parties, ["entity_id", "name_bn", "name_en", "acronym", "category"])
    save_csv("food_dining.csv", food, ["entity_id", "name_bn", "name_en", "category"])
    save_csv("public_figures.csv", public_figures, ["entity_id", "name_bn", "name_en", "acronym", "category"])
    save_csv("common_services.csv", common_services, ["entity_id", "name_bn", "name_en", "acronym", "category"])
    save_csv("casual_banglish.csv", casual_banglish, ["banglish", "name_bn", "category"])
    save_csv("cultural_figures.csv", cultural_figures, ["entity_id", "name_bn", "name_en", "profession", "category"])
    save_csv("heritage_sites.csv", heritage_sites, ["entity_id", "name_bn", "name_en", "religion", "category"])
    print("All categories crawled and saved successfully.")

if __name__ == "__main__":
    main()
