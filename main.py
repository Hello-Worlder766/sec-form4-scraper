import requests
import re
import xml.etree.ElementTree as ET
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

print(">>> Running main.py from:", os.path.abspath(__file__))

# ---------------------------------------------
# Load Google Sheets credentials
# ---------------------------------------------
google_creds = json.loads(os.environ["GOOGLE_SHEETS_KEY"])

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
client = gspread.authorize(creds)

sheet_id = os.environ["SHEET_ID"]
sheet = client.open_by_key(sheet_id).worksheet("Trades")

# ---------------------------------------------
# SEC source page (NOT RSS — HTML filings table)
# ---------------------------------------------
RSS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4"

# ---------------------------------------------
# Fetch Form 4 URLs from live SEC HTML page
# ---------------------------------------------
def fetch_form4_urls():
    headers = {"User-Agent": "insidesignal/1.0"}
    html = requests.get(RSS_URL, headers=headers).text

    print("\n===== DEBUG HTML FIRST 500 CHARS =====")
    print(html[:500])
    print("\n===== DEBUG HTML DONE =====\n")

    # TEMP: we stop here so the rest of the scraper doesn't run
    return []

    for accession, cik in matches:
        acc_clean = accession.replace("-", "")
        cik_clean = cik.lstrip("0")  # SEC folder removes leading zeros

        xml_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_clean}/{acc_clean}/xslF345X03/doc.xml"
        )
        urls.append(xml_url)

    print("Sample URLs:", urls[:5])
    return urls

# ---------------------------------------------
# Parse a single Form 4 XML
# ---------------------------------------------
def parse_form4(xml_url):
    try:
        resp = requests.get(xml_url, headers={"User-Agent": "insidesignal/1.0"})
        if resp.status_code != 200:
            print("   Skipping (HTTP", resp.status_code, "):", xml_url)
            return None

        root = ET.fromstring(resp.text)

        issuer_node = root.find(".//issuer/issuerName")
        company = issuer_node.text if issuer_node is not None else ""

        reporting = root.find(".//reportingOwner")
        insider = reporting.find(".//rptOwnerName").text if reporting is not None else ""
        role_node = reporting.find(".//rptOwnerRelationship/officerTitle")
        role = role_node.text if role_node is not None else ""

        # Sum transaction values
        total_amount = 0
        shares_out = 0
        price_out = 0

        for txn in root.findall(".//nonDerivativeTransaction"):
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

        # Only report big trades
        if total_amount >= 5_000_000:
            print(f"   ✅ {company} — {insider} — ${total_amount:,.0f}")
            return {
                "company": company,
                "ticker": "",  # you can add later
                "insider": insider,
                "role": role,
                "shares": shares_out,
                "price": price_out,
                "amount": total_amount,
                "link": xml_url,
            }

        return None

    except Exception as e:
        print("Error parsing XML:", xml_url, e)
        return None

# ---------------------------------------------
# Write results to Google Sheets
# ---------------------------------------------
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

# ---------------------------------------------
# MAIN
# ---------------------------------------------
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
