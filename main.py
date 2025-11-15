import requests
import xml.etree.ElementTree as ET
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

print(">>> Running main.py from:", os.path.abspath(__file__))

# Load Google credentials
google_creds = json.loads(os.environ["GOOGLE_SHEETS_KEY"])

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
client = gspread.authorize(creds)

sheet_id = os.environ["SHEET_ID"]
sheet = client.open_by_key(sheet_id).worksheet("Trades")

# --- REAL SEC Atom feed ---
ATOM_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&owner=only&output=atom"


def fetch_form4_urls():
    headers = {"User-Agent": "insidesignal/1.0"}
    xml_text = requests.get(ATOM_URL, headers=headers).text

    print("Fetched SEC Atom feed length:", len(xml_text))

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        print("XML Parse Error:", e)
        return []

    # Atom feed structure: <entry><id>...Accession...CIK...</id></entry>
    entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    print("Atom entries found:", len(entries))

    urls = []
    for entry in entries:
        # Filing detail page
        link = entry.find("{http://www.w3.org/2005/Atom}link")
        if link is None:
            continue

        href = link.get("href")
        if not href:
            continue

        # Convert filing detail URL → XML doc URL
        # Example detail URL:
        #   https://www.sec.gov/Archives/edgar/data/1234/0001234-25-00001-index.html
        #
        # Convert to:
        #   https://www.sec.gov/Archives/edgar/data/1234/00012342500001/xslF345X03/doc.xml

        try:
            parts = href.replace("-index.html", "").split("/")
            cik = parts[-2]
            acc_no = parts[-1].replace("-", "")
            xml_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no}/xslF345X03/doc.xml"
            urls.append(xml_url)
        except Exception:
            continue

    print("Final XML URLs extracted:", len(urls))
    return urls


def parse_form4(xml_url):
    headers = {"User-Agent": "insidesignal/1.0"}
    resp = requests.get(xml_url, headers=headers)

    if resp.status_code != 200:
        return None

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
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

        amount = shares * price
        total_amount += amount
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
    urls = fetch_form4_urls()
    results = []

    for url in urls:
        parsed = parse_form4(url)
        if parsed:
            results.append(parsed)

    print("Trades >= $5M found:", len(results))
    write_to_sheet(results)
    print("Done.")


if __name__ == "__main__":
    main()
