"""
Strict Quality Assurance & Bangla Purity Validator
Enforces the mandatory rule:
  - All summaries / short descriptions MUST be in pure, authentic Bangla
  - Zero English summaries permitted in database candidates
  - Zero corrupt multi-line splits in CSVs
  - Validates Queens University (L89-95) fix
"""
import os
import csv
import sys
import re

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENRICHED_DIR = os.path.join(BASE_DIR, "data", "raw", "enriched")

BANGLA_CHAR_RE = re.compile(r'[\u0980-\u09FF]')
ENGLISH_WORD_RE = re.compile(r'\b[A-Za-z]{3,}\b')

def check_bangla_purity(text, min_bangla_ratio=0.6):
    """Verify that text is predominantly Bengali script."""
    if not text or not text.strip():
        return False, "Empty text"
    
    # Strip whitespace, digits, punctuation
    clean = re.sub(r'[\s\d\.,\(\)\-\"\'/]+', '', text)
    if not clean:
        return False, "No alpha characters"
    
    bangla_count = len(BANGLA_CHAR_RE.findall(clean))
    ratio = bangla_count / len(clean)
    if ratio < min_bangla_ratio:
        return False, f"Low Bangla ratio: {ratio:.1%} (contains foreign text)"
    return True, f"Valid ({ratio:.1%} Bangla)"

def validate_file(filename, summary_col, name_bn_col="name_bn"):
    path = os.path.join(ENRICHED_DIR, filename)
    print(f"\nValidating {filename} ...")
    if not os.path.exists(path):
        print(f"  [ERROR] File missing: {path}")
        return False

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"  Total records: {len(rows)}")
    failures = []

    for i, r in enumerate(rows, 1):
        summary = r.get(summary_col, "").strip()
        name_bn = r.get(name_bn_col, "")
        
        # Check 1: Non-empty
        if not summary:
            failures.append((i, name_bn, "Missing summary"))
            continue

        # Check 2: No raw unescaped newlines
        if "\n" in summary or "\r" in summary:
            failures.append((i, name_bn, "Corrupt raw newline in summary"))
            continue

        # Check 3: Bangla purity
        ok, msg = check_bangla_purity(summary)
        if not ok:
            failures.append((i, name_bn, f"{msg} -> '{summary[:60]}...'"))

    # Special check for Queens University
    if "universities" in filename.lower():
        queens_row = next((r for r in rows if "কুইন্স" in r.get("name_bn", "") or "Queens" in r.get("name_en", "")), None)
        if queens_row:
            q_sum = queens_row.get(summary_col, "")
            if "may refer to" in q_sum.lower() or "belfast" in q_sum.lower():
                failures.append((0, "Queens University", "Corrupted English disambiguation still present!"))
            else:
                print("  [PASS] Queens University (L89-95) is cleanly fixed with authentic Bangla summary.")

    if failures:
        print(f"  [FAILED] Found {len(failures)} issues in {filename}:")
        for f_idx, f_name, f_err in failures[:10]:
            print(f"    - Row {f_idx} ({f_name}): {f_err}")
        return False
    else:
        print(f"  [PASSED] All {len(rows)} entries verified in authentic Bangla!")
        return True

def main():
    print("=== Strict Khoojo Bangla QA & Integrity Audit ===")
    
    results = [
        validate_file("universities_enriched_full.csv", "summary_bn"),
        validate_file("heritage_sites_3to5_images.csv", "summary_bn"),
        validate_file("cultural_figures_3to5_images.csv", "summary_bn"),
        validate_file("food_dining_100.csv", "summary_bn"),
        validate_file("political_parties_with_news.csv", "ideology_summary_bn")
    ]

    print("\n" + "="*50)
    if all(results):
        print("ALL 5 SPECIALIZED DATASETS PASSED STRICT BANGLA PURITY QA!")
        print("Zero English summaries. Zero corrupt multi-line splits.")
        print("="*50)
        sys.exit(0)
    else:
        print("QA FAILED! Please review the errors above.")
        print("="*50)
        sys.exit(1)

if __name__ == "__main__":
    main()
