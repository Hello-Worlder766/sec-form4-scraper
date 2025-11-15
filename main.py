import requests
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

print(">>> Running main.py from:", os.path.abspath(__file__))

# -----------------------------------------
# GOOGLE SHEETS AUTH
# -----------------------------------------
google_creds = json.loads(os.environ["GOOGLE_SHEETS_KEY"])

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
client = gspread.authorize(creds)

sheet_id = os.environ["SHEET_ID"]
sheet = client.open_by_key(sheet_id).worksheet("Trades")

# SEC latest forms page
RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4"


# -----------------------------------------
# FETCH FORM 4 PAGE (DEBUG MODE)
# -----------------------------------------
def fetch_form4_urls():
    headers = {"User-Agent": "insidesignal/1.0"}

    try:
        html = requests.get(RSS_URL, headers=headers).text
    except Exception as e:
        print(">>> ERROR FETCHING SEC PAGE:", e)
        return []

    print("\n=== SEC PAGE DEBUG ===")
    print("Fetched SEC page length:", len(html))
    print("\n--- BEGIN RAW HTML (first 5000 chars) ---\n")
    print(html[:5000])
    print("\n--- END RAW HTML ---\n")
    print("=====================================================\n")

    # TEMPORARILY return no URLs until we analyze the raw HTML
    return []


# -----------------------------------------
# PARSE FORM 4 XML (will be used after debugging)
# -----------------------------------------
def parse_form4(xml_url):
    return None  # Temporarily disabled until we finish HTML parsing


# -----------------------------------------
# WRITE RESULTS TO GOOGLE SHEETS
# -----------------------------------------
def write_to_sheet(rows):
    sheet.clear()
    sheet.append_row([
        "Date", "Company", "Ticker", "Insider", "Role",
        "Shares", "Price", "Amount", "Link"
    ])

    today = datetime.now().strftime("%Y-%m-%d")

    for r in rows:
        sheet.append_row([
            today,
            r.get("company", ""),
            r.get("ticker", ""),
            r.get("insider", ""),
            r.get("role", ""),
            r.get("shares", ""),
            r.get("price", ""),
            r.get("amount", ""),
            r.get("link", ""),
        ])


# -----------------------------------------
# MAIN EXECUTION
# -----------------------------------------
def main():
    urls = fetch_form4_urls()

    print("Found URLs:", len(urls))

    results = []
    for url in urls:
        parsed = parse_form4(url)
        if parsed:
            results.append(parsed)

    print("Final big trades:", len(results))
    write_to_sheet(results)


if __name__ == "__main__":
    main()
