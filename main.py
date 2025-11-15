import requests
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

print(">>> Running main.py:", os.path.abspath(__file__))

# Load Google credentials
google_creds = json.loads(os.environ["GOOGLE_SHEETS_KEY"])

scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
client = gspread.authorize(creds)

sheet_id = os.environ["SHEET_ID"]
sheet = client.open_by_key(sheet_id).worksheet("Trades")

# 🔥 REAL WORKING JSON FEED
SEC_JSON_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&owner=only&output=json"


def fetch_form4_json():
    headers = {"User-Agent": "insidesignal/1.0"}
    r = requests.get(SEC_JSON_URL, headers=headers)
    print("Fetched SEC JSON length:", len(r.text))

    try:
        data = r.json()
    except:
        print("SEC JSON parse error")
        return []

    items = data.get("filings", {}).get("recent", {})
    print("Items present:", len(items.get("accessionNumber", [])))

    results = []
    for i in range(len(items["accessionNumber"])):
        accession = items["accessionNumber"][i].replace("-", "")
        cik = items["cik"][i]

        xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/xslF345X03/doc.xml"
        results.append(xml_url)

    print("Final XML URLs:", len(results))
    return results


def parse_form4(xml_url):
    headers = {"User-Agent": "insidesignal/1.0"}
    resp = requests.get(xml_url, headers=headers)
    if resp.status_code != 200:
        return None

    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(resp.text)
    except:
        return None

    issuer = root.find(".//issuer/issuerName")
    company = issuer.text if issuer is not None else ""

    reporting = root.find(".//reportingOwner")
    insider = reporting.find(".//rptOwnerName").text if reporting is not None else ""
    role_node = reporting.find(".//rptOwnerRelationship/officerTitle")
    role = role_node.text if role_node is not None else ""

    txn_nodes = root.findall(".//nonDerivativeTransaction")

    total_amount = 0
    shares_out = 0
    price_out = 0

    for txn in txn_nodes:
        shares_node = txn.find(".//transactionShares/value")
        price_node = txn.find(".//transactionPricePerShare/value")
        if shares_node is None or price_node is None:
            continue

        try:
            shares = float(shares_node.text)
            price = float(price_node.text)
        except:
            continue

        total_amount += shares * price
        shares_out = shares
        price_out = price

    if total_amount >= 5_000_000:
        return {
            "company": company,
            "ticker": "",
            "insider": insider,
            "role": role,
            "shares": shares_out,
            "price": price_out,
            "amount": total_amount,
            "link": xml_url,
        }

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
            today, r["company"], r["ticker"], r["insider"],
            r["role"], r["shares"], r["price"], r["amount"], r["link"]
        ])


def main():
    urls = fetch_form4_json()
    print(">>> URLS FOUND:", len(urls))

    results = []
    for url in urls:
        parsed = parse_form4(url)
        if parsed:
            results.append(parsed)

    print(">>> TRADES >= $5M:", len(results))
    write_to_sheet(results)
    print("Done.")


if __name__ == "__main__":
    main()
