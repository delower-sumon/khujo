import os
import csv
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import StringIO
import csv
import pandas as pd
import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw")
os.makedirs(DATA_DIR, exist_ok=True)

def save_csv(filename, data, fieldnames):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Saved {len(data)} entries to {filepath}")

def clean_text(text):
    if not isinstance(text, str):
        return ""
    # Remove citations like [1], [2]
    import re
    text = re.sub(r'\[\d+\]', '', text)
    return text.strip()

def crawl_universities():
    url = "https://en.wikipedia.org/wiki/List_of_universities_in_Bangladesh"
    print(f"Crawling universities from {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Tables are sortable wiki tables
    tables = soup.find_all('table', {'class': 'wikitable'})
    
    uni_data = []
    uni_count = 0
    
    for table in tables:
        try:
            df = pd.read_html(StringIO(str(table)), flavor='html5lib')[0]
            
            # Identify the name column
            name_col = None
            for col in ['University[a]', 'University', 'Colleges', 'Name']:
                if col in df.columns:
                    name_col = col
                    break
                    
            if name_col:
                for idx, row in df.iterrows():
                    name_en = clean_text(row.get(name_col, ''))
                    acronym = clean_text(row.get('Acronym', ''))
                    if pd.isna(acronym):
                        acronym = ''
                    
                    if name_en:
                        uni_count += 1
                        uni_data.append({
                            "entity_id": f"uni_crawler_{uni_count}",
                            "name_bn": "", # We will need to map these later or rely on english for now
                            "name_en": name_en,
                            "acronym": acronym,
                            "category": "Universities"
                        })
        except Exception as e:
            print(f"Skipping a table due to error: {e}")
            continue
    
    # Merge with previous high quality list for bangla names
    # We will just write this to a new file universities_full.csv
    save_csv("universities_full.csv", uni_data, ["entity_id", "name_bn", "name_en", "acronym", "category"])
    return uni_data

def crawl_political_parties():
    url = "https://en.wikipedia.org/wiki/List_of_political_parties_in_Bangladesh"
    print(f"Crawling political parties from {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    tables = soup.find_all('table', {'class': 'wikitable'})
    
    pol_data = []
    pol_count = 0
    
    for table in tables:
        try:
            df = pd.read_html(StringIO(str(table)), flavor='html5lib')[0]
            if 'English name' in df.columns or 'Name' in df.columns or 'Party' in df.columns:
                name_col = 'English name' if 'English name' in df.columns else ('Party' if 'Party' in df.columns else 'Name')
                for idx, row in df.iterrows():
                    name_en = clean_text(str(row.get(name_col, '')))
                    abbr = clean_text(str(row.get('Abbreviation', row.get('Abbr.', ''))))
                    if pd.isna(abbr) or abbr == 'nan':
                        abbr = ''
                    if name_en and name_en != 'nan':
                        pol_count += 1
                        pol_data.append({
                            "entity_id": f"pol_crawler_{pol_count}",
                            "name_bn": "",
                            "name_en": name_en,
                            "acronym": abbr,
                            "category": "Political Parties"
                        })
        except Exception as e:
            continue
            
    save_csv("political_parties_full.csv", pol_data, ["entity_id", "name_bn", "name_en", "acronym", "category"])
    return pol_data

# Expanded static lists for Banglish, Food, Services, Figures
food = [
    {"entity_id": f"food_{i}", "name_bn": bn, "name_en": en, "category": "Food & Dining"}
    for i, (bn, en) in enumerate([
        ("ফুচকা", "Puchka"), ("বিরিয়ানি", "Biryani"), ("কাচ্চি বিরিয়ানি", "Kacchi Biryani"),
        ("তেহারি", "Tehari"), ("চটপটি", "Chotpoti"), ("রসগোল্লা", "Roshogolla"),
        ("মিষ্টি দই", "Mishti Doi"), ("ভর্তা", "Bhorta"), ("ইলিশ ভাজা", "Fried Hilsa"),
        ("পান্তা ভাত", "Panta Bhat"), ("হালিম", "Haleem"), ("বোরহানি", "Borhani"),
        ("ঝালমুড়ি", "Jhalmuri"), ("সমুচা", "Samosa"), ("সিঙ্গারা", "Singara"),
        ("জিলাপি", "Jalebi"), ("শুটকি", "Shutki"), ("খাসির মাংস", "Mutton Curry"),
        ("গরুর ভুনা", "Beef Bhuna"), ("ডাল", "Dal"), ("আলু ভর্তা", "Alu Bhorta"),
        ("বেসনের বড়া", "Besan Bora"), ("পিঠা", "Pitha"), ("ভাপা পিঠা", "Bhapa Pitha"),
        ("চিতই পিঠা", "Chitoi Pitha"), ("পাটিসাপটা", "Patishapta"), ("নারু", "Naru"),
        ("মোয়া", "Moa"), ("কদম", "Kodom"), ("চমচম", "Chomchom")
    ])
]

casual_banglish = [
    {"banglish": b, "name_bn": bn, "category": "Casual Banglish"}
    for b, bn in [
        ("manush", "মানুষ"), ("desh", "দেশ"), ("valo", "ভালো"), ("khabar", "খাবার"),
        ("kothay", "কোথায়"), ("taka", "টাকা"), ("ami", "আমি"), ("tumi", "তুমি"),
        ("bari", "বাড়ি"), ("rasta", "রাস্তা"), ("cholo", "চলো"), ("ajke", "আজকে"),
        ("kalke", "কালকে"), ("jam", "জ্যাম"), ("bazar", "বাজার"), ("dokan", "দোকান"),
        ("koto", "কত"), ("kemon", "কেমন"), ("ki", "কী"), ("shomoy", "সময়"),
        ("din", "দিন"), ("rat", "রাত"), ("sokal", "সকাল"), ("bikale", "বিকালে"),
        ("bristi", "বৃষ্টি"), ("rod", "রোদ"), ("garam", "গরম"), ("thanda", "ঠান্ডা"),
        ("onek", "অনেক"), ("kom", "কম"), ("beshi", "বেশি"), ("ekhon", "এখন"),
        ("pore", "পরে"), ("age", "আগে"), ("notun", "নতুন"), ("puran", "পুরান"),
        ("valo na", "ভালো না"), ("sundor", "সুন্দর"), ("boka", "বোকা"), ("pagol", "পাগল")
    ]
]

public_figures = [
    {"entity_id": f"fig_{i}", "name_bn": bn, "name_en": en, "acronym": acr, "category": "Public Figures"}
    for i, (bn, en, acr) in enumerate([
        ("প্রধানমন্ত্রী", "Prime Minister", "PM"), ("রাষ্ট্রপতি", "President", ""),
        ("শিক্ষামন্ত্রী", "Education Minister", ""), ("স্বরাষ্ট্রমন্ত্রী", "Home Minister", ""),
        ("মেয়র", "Mayor", ""), ("প্রধান বিচারপতি", "Chief Justice", "CJ"),
        ("সেনাপ্রধান", "Army Chief", ""), ("আইজিপি", "Inspector General of Police", "IGP"),
        ("অর্থমন্ত্রী", "Finance Minister", ""), ("পররাষ্ট্রমন্ত্রী", "Foreign Minister", ""),
        ("তথ্যমন্ত্রী", "Information Minister", ""), ("স্বাস্থ্যমন্ত্রী", "Health Minister", ""),
        ("কৃষিমন্ত্রী", "Agriculture Minister", ""), ("শিল্পমন্ত্রী", "Industries Minister", ""),
        ("বাণিজ্যমন্ত্রী", "Commerce Minister", ""), ("আইনমন্ত্রী", "Law Minister", ""),
        ("বিদ্যুৎমন্ত্রী", "Power Minister", ""), ("খাদ্যমন্ত্রী", "Food Minister", ""),
        ("পরিকল্পনামন্ত্রী", "Planning Minister", ""), ("ভূমিমন্ত্রী", "Land Minister", "")
    ])
]

common_services = [
    {"entity_id": f"srv_{i}", "name_bn": bn, "name_en": en, "acronym": acr, "category": "Common Services"}
    for i, (bn, en, acr) in enumerate([
        ("হাসপাতাল", "Hospital", ""), ("থানা", "Police Station", "PS"),
        ("ফায়ার সার্ভিস", "Fire Service", ""), ("রেলওয়ে স্টেশন", "Railway Station", ""),
        ("বিমানবন্দর", "Airport", ""), ("পোস্ট অফিস", "Post Office", ""),
        ("ব্যাংক", "Bank", ""), ("এটিএম", "ATM", "ATM"),
        ("ফার্মেসি", "Pharmacy", ""), ("রেস্তোরাঁ", "Restaurant", ""),
        ("বাস স্ট্যান্ড", "Bus Stand", ""), ("লঞ্চ ঘাট", "Launch Terminal", ""),
        ("পাসপোর্ট অফিস", "Passport Office", ""), ("বিআরটিএ", "BRTA", "BRTA"),
        ("ওয়াসা", "WASA", "WASA"), ("ডেস্কো", "DESCO", "DESCO"),
        ("টিতাশ গ্যাস", "Titas Gas", ""), ("সিটি কর্পোরেশন", "City Corporation", ""),
        ("উপজেলা পরিষদ", "Upazila Parishad", ""), ("ইউনিয়ন পরিষদ", "Union Parishad", "")
    ])
]

cultural_figures = [
    {"entity_id": f"cult_{i}", "name_bn": bn, "name_en": en, "profession": prof, "category": "Cultural Figures"}
    for i, (bn, en, prof) in enumerate([
        ("কাজী নজরুল ইসলাম", "Kazi Nazrul Islam", "Poet"), ("রবীন্দ্রনাথ ঠাকুর", "Rabindranath Tagore", "Poet"),
        ("বঙ্গবন্ধু শেখ মুজিবুর রহমান", "Bangabandhu Sheikh Mujibur Rahman", "Founding Father"),
        ("মাওলানা আবদুল হামিদ খান ভাসানী", "Maulana Abdul Hamid Khan Bhashani", "Politician"),
        ("শেরে বাংলা এ. কে. ফজলুল হক", "A. K. Fazlul Huq", "Politician"), ("জসীমউদ্দীন", "Jasimuddin", "Poet"),
        ("জয়নুল আবেদিন", "Zainul Abedin", "Painter"), ("এস এম সুলতান", "S M Sultan", "Painter"),
        ("হুমায়ূন আহমেদ", "Humayun Ahmed", "Writer"), ("বেগম রোকেয়া", "Begum Rokeya", "Writer"),
        ("জীবনানন্দ দাশ", "Jibanananda Das", "Poet"), ("মুহম্মদ শহীদুল্লাহ", "Muhammad Shahidullah", "Linguist"),
        ("জগদীশ চন্দ্র বসু", "Jagadish Chandra Bose", "Scientist"), ("সত্যেন্দ্রনাথ বসু", "Satyendra Nath Bose", "Scientist"),
        ("তারেক মাসুদ", "Tareque Masud", "Filmmaker"), ("সত্যজিৎ রায়", "Satyajit Ray", "Filmmaker"),
        ("ঋত্বিক ঘটক", "Ritwik Ghatak", "Filmmaker"), ("মুনীর চৌধুরী", "Munier Choudhury", "Playwright"),
        ("শহীদুল্লা কায়সার", "Shahidullah Kaiser", "Novelist"), ("জহির রায়হান", "Zahir Raihan", "Filmmaker"),
        ("কামরুল হাসান", "Quamrul Hassan", "Painter"), ("শামসুর রাহমান", "Shamsur Rahman", "Poet")
    ])
]

heritage_sites = [
    {"entity_id": f"heri_{i}", "name_bn": bn, "name_en": en, "religion": rel, "category": "Heritage Sites"}
    for i, (bn, en, rel) in enumerate([
        ("বায়তুল মোকাররম জাতীয় মসজিদ", "Baitul Mukarram National Mosque", "Islam"),
        ("ঢাকেশ্বরী জাতীয় মন্দির", "Dhakeshwari National Temple", "Hinduism"),
        ("আর্মেনীয় গির্জা", "Armenian Church", "Christianity"), ("ষাট গম্বুজ মসজিদ", "Sixty Dome Mosque", "Islam"),
        ("কান্তজীর মন্দির", "Kantajew Temple", "Hinduism"), ("সোমপুর মহাবিহার", "Somapura Mahavihara", "Buddhism"),
        ("তারা মসজিদ", "Star Mosque", "Islam"), ("লালবাগ কেল্লা", "Lalbagh Fort", "Historical"),
        ("আহসান মঞ্জিল", "Ahsan Manzil", "Historical"), ("ময়নামতি", "Mainamati", "Buddhism"),
        ("মহাস্থানগড়", "Mahasthangarh", "Historical"), ("ছোট সোনা মসজিদ", "Chhota Sona Mosque", "Islam"),
        ("পানাম নগর", "Panam Nagar", "Historical"), ("শহীদ মিনার", "Shaheed Minar", "Monument"),
        ("জাতীয় স্মৃতিসৌধ", "National Martyrs' Memorial", "Monument"), ("মুজিবনগর স্মৃতিসৌধ", "Mujibnagar Memorial", "Monument"),
        ("রামসাগর", "Ramsagar", "Historical"), ("تاجহাট রাজবাড়ি", "Tajhat Palace", "Historical"),
        ("উত্তরা গণভবন", "Uttara Gonobhaban", "Historical"), ("পুঠিয়া রাজবাড়ী", "Puthia Temple Complex", "Hinduism")
    ])
]


def main():
    print(f"Saving expanded high-quality data to: {DATA_DIR}")
    
    # 1. Fetch real universities and political parties from Wikipedia
    crawl_universities()
    crawl_political_parties()
    
    # 2. Save expanded static lists
    save_csv("food_dining_full.csv", food, ["entity_id", "name_bn", "name_en", "category"])
    save_csv("public_figures_full.csv", public_figures, ["entity_id", "name_bn", "name_en", "acronym", "category"])
    save_csv("common_services_full.csv", common_services, ["entity_id", "name_bn", "name_en", "acronym", "category"])
    save_csv("casual_banglish_full.csv", casual_banglish, ["banglish", "name_bn", "category"])
    save_csv("cultural_figures_full.csv", cultural_figures, ["entity_id", "name_bn", "name_en", "profession", "category"])
    save_csv("heritage_sites_full.csv", heritage_sites, ["entity_id", "name_bn", "name_en", "religion", "category"])
    print("All expanded categories crawled and saved successfully.")

if __name__ == "__main__":
    main()
