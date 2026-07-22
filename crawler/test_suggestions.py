import requests
import sys
sys.stdout.reconfigure(encoding='utf-8')

test_inputs = ["pro", "ঢাকা", "গুগল", "face", "উইকি", "bangla"]

for q in test_inputs:
    res = requests.get(f"http://localhost:8000/api/v1/suggestions?q={q}").json()
    print(f"Suggestions for '{q}': {res}")
