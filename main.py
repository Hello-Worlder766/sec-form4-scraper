import os
import json
import requests

print(">>> main.py is running!")
print(">>> Current path:", os.path.abspath(__file__))

# --- Test #1: Verify secrets are readable ---
try:
    key = os.environ["GOOGLE_SHEETS_KEY"]
    print(">>> GOOGLE_SHEETS_KEY length:", len(key))
except Exception as e:
    print("!!! ERROR: GOOGLE_SHEETS_KEY not found:", e)

try:
    sid = os.environ["SHEET_ID"]
    print(">>> SHEET_ID loaded:", sid)
except Exception as e:
    print("!!! ERROR: SHEET_ID not found:", e)

# --- Test #2: Make a simple ping to Google ---
try:
    resp = requests.get("https://www.google.com", timeout=5)
    print(">>> Google ping status:", resp.status_code)
except Exception as e:
    print("!!! ERROR pinging Google:", e)

# --- Test #3: Ping SEC---
try:
    resp2 = requests.get("https://www.sec.gov", headers={"User-Agent": "insidesignal-test"}, timeout=5)
    print(">>> SEC ping status:", resp2.status_code)
except Exception as e:
    print("!!! ERROR pinging SEC:", e)

print(">>> TEST COMPLETE <<<")
