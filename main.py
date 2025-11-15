import requests
import xml.etree.ElementTree as ET
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

print(">>> Running main.py from:", os.path.abspath(__file__))

# Load Google credentials from GitHub Secret
google_creds = json.loads(os.environ["GOOGLE_SHEETS_KEY"])

# Google Sheets setup
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
client = gspread.authorize(creds)

sheet_id = os.environ["SHEET_ID"]
sheet = client.open_by_key(sheet_id).worksheet("Trades")


# ----------------------------------------------------------
# USE THE JSON "recent filings" endpoint
# ----------------------------------------------------------
JSON_URL = "https://data.sec.gov/submissions/CIK0000320193.json"  # Apple CIK to test connectivity

HEADERS = {
    "User-Agent": "InsideSignalTrader/1.0 contact@example.com"
}


def fetch_recent_form4s_json():
    """
    Uses SEC's JSON submissions API instead of the broken HTML feed.
    We first hit Apple (AAPL) just to confirm SEC allows our User-Agent.
    Then we fetch ALL recent filings from the public filings feed.
    """
    print(">>> Testing connectivity with Apple JSON…")

    try:
        test = requests.get(JSON_URL, headers=HEADERS)
        print("Test status:", test.status_code)
    except Exception as e:
        print("Request error:", e)
        return []

    # Now hit the REAL Form 4 feed
    print(">>> Fetching master filings…")
    url = "https://data.sec.gov/rss?formType=4&excludeDocuments=true"

    try:
        resp = requests.get(url, headers=HEADERS)
        print("Master feed status:", resp.status_code)
        text = resp.text
    except Exception as e:
        print("Master feed crashed:", e)
        return []

    # Parse the feed
    urls = []

    for line in text.splitlines():
        if "edgar/data" in line and "xml" in line:
            line = line.strip()
            start = line.find("https://")
            end = line.find(".xml") + 4
            if start != -1 and end != -1:
                xml_url = line[start:end]
                urls.append(xml_url)

    print(">>> Found URLs:", len(urls))
    return urls


def parse_form4(xml_url):
    """
    Extracts trade size and info from a single Form 4 XML.
    Only keeps trades >= $5M.
    """
    try:
        resp = requests.get(xml_url, headers=HEADERS)
        if resp.status_code != 200:
            return None

        root = ET.fromstring(resp.text)

        issuer = root.find(".//issuer/issuerName")
        company = issuer.text if issuer is not None else ""

        reporting = root.find(".//reportingOwner")
        insider = reporting.find(".//rptOwnerName").text if reporting is not None else ""
        role_node = reporting.find(".//rptOwnerRelationship/officerTitle")
        role = role_node.text if role_node is not None else ""

        txn_nodes = root.findall(".//nonDerivativeTransaction")

        total = 0
        last_shares = 0
        last_price = 0

        for txn in txn_nodes:
            shares = txn.find(".//transactionShares/value")
            price = txn.find(".//transactionPricePerShare/value")
            if shares is None or price is None:
                continue
            try:
                s = float(shares.text)
                p = float(price.text)
            except:
                continue

            total += s * p
            last_shares = s
            last_price = p

        if total >= 5_000_000:
            print(">>> Big trade:", company, insider, total)
            return {
                "company": company,
                "ticker": "",
                "insider": insider,
                "role": role,
                "shares": last_shares,
                "price": last_price,
                "amount": total,
                "link": xml_url,
            }

    except Exception as e:
        print("Parse error:", e)
        return None

    return None


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
            r["company"],
            r["ticker"],
            r["insider"],
            r["role"],
            r["shares"],
            r["price"],
            r["amount"],
            r["link"],
        ])


def main():
    urls = fetch_recent_form4s_json()

    print(">>> URLs found:", len(urls))

    results = []
    for url in urls:
        data = parse_form4(url)
        if data:
            results.append(data)

    print(">>> Final big trades:", len(results))

    write_to_sheet(results)


if __name__ == "__main__":
    main()
