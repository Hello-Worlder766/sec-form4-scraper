import requests
import xml.etree.ElementTree as ET
import json
import os
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

print(">>> Running main.py from:", os.path.abspath(__file__))

# ---- Google Sheets setup ----
google_creds = json.loads(os.environ["GOOGLE_SHEETS_KEY"])

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
client = gspread.authorize(creds)

sheet_id = os.environ["SHEET_ID"]
sheet = client.open_by_key(sheet_id).worksheet("Trades")

# ---- SEC URL ----
FILINGS_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4"


def fetch_form4_urls():
    """Extract CIK + accession from SEC HTML using regex."""
    headers = {"User-Agent": "insidesignal/1.0"}

    html = requests.get(FILINGS_URL, headers=headers).text
    print("Fetched SEC page length:", len(html))

    import re
    # Matches CIK=(digits) and accession number blocks
    patterns = [
        r"CIK=(\d+)&amp;Acc-no=([0-9\-]+)",
        r"CIK=(\d+)&Acc-no=([0-9\-]+)",
    ]

    urls = []

    for pattern in patterns:
        matches = re.findall(pattern, html)
        for cik, acc in matches:
            acc = acc.replace("-", "")
            cik = str(int(cik))  # remove leading zeros
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/xslF345X03/doc.xml"
            urls.append(url)

    print("Found URLs:", len(urls))
    return urls


def parse_form4(url):
    """Download XML and extract big trades."""
    try:
        resp = requests.get(url, headers={"User-Agent": "insidesignal/1.0"})
        if resp.status_code != 200:
            return None

        root = ET.fromstring(resp.text)

        issuer = root.find(".//issuer/issuerName")
        company = issuer.text if issuer is not None else ""

        reporting = root.find(".//reportingOwner")
        insider = reporting.find(".//rptOwnerName").text if reporting is not None else ""

        role_node = reporting.find(".//rptOwnerRelationship/officerTitle")
        role = role_node.text if role_node is not None else ""

        total = 0
        shares_out = 0
        price_out = 0

        for t in root.findall(".//nonDerivativeTransaction"):
            s = t.find(".//transactionShares/value")
            p = t.find(".//transactionPricePerShare/value")

            if s is None or p is None:
                continue

            try:
                shares = float(s.text)
                price = float(p.text)
                total += shares * price
                shares_out = shares
                price_out = price
            except:
                continue

        if total >= 5_000_000:
            print("BIG TRADE:", company, insider, total)
            return {
                "company": company,
                "ticker": "",
                "insider": insider,
                "role": role,
                "shares": shares_out,
                "price": price_out,
                "amount": total,
                "link": url
            }

    except Exception as e:
        print("Error parsing", url, e)
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
            today, r["company"], r["ticker"], r["insider"], r["role"],
            r["shares"], r["price"], r["amount"], r["link"]
        ])


def main():
    urls = fetch_form4_urls()
    big_trades = []

    for u in urls:
        x = parse_form4(u)
        if x:
            big_trades.append(x)

    print("Final big trades:", len(big_trades))
    write_to_sheet(big_trades)


if __name__ == "__main__":
    main()
