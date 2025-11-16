import requests
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

SEC_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4"

def fetch_html():
    headers = {
        "User-Agent": "InsideSignalTrader (nate@example.com)",
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov"
    }
    r = requests.get(SEC_URL, headers=headers)
    print("Fetched HTML length:", len(r.text))
    return r.text

def extract_accessions(html):
    import re
    pattern = re.compile(r"Accession Number:\s+([0-9\-]+)", re.MULTILINE)
    matches = pattern.findall(html)
    print("Found Accessions:", len(matches))
    return matches

def push_to_sheet(rows):
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_json = json.loads(os.environ["GOOGLE_SHEETS_KEY"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
    client = gspread.authorize(creds)

    sheet_id = os.environ["SHEET_ID"]
    sh = client.open_by_key(sheet_id).sheet1

    sh.clear()
    sh.append_row(["Date", "Accession"])

    today = datetime.now().strftime("%Y-%m-%d")
    for acc in rows:
        sh.append_row([today, acc])

def main():
    html = fetch_html()
    accessions = extract_accessions(html)
    push_to_sheet(accessions)
    print("Done.")

if __name__ == "__main__":
    main()
