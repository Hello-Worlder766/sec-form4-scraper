import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta

import gspread
from oauth2client.service_account import ServiceAccountCredentials

print(">>> Running main.py from:", os.path.abspath(__file__))

# ----------------------------------------------------------
# Google Sheets setup
# ----------------------------------------------------------
google_creds = json.loads(os.environ["GOOGLE_SHEETS_KEY"])

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(google_creds, scope)
client = gspread.authorize(creds)

sheet_id = os.environ["SHEET_ID"]
sheet = client.open_by_key(sheet_id).worksheet("Trades")

# Daily index base
DAILY_INDEX_BASE = "https://www.sec.gov/Archives/edgar/daily-index"

# IMPORTANT: real, descriptive User-Agent per SEC guidelines
SEC_HEADERS = {
    "User-Agent": (
        "InsideSignalTrader-Form4-Scraper/1.0 "
        "(Contact: nate@example.com; GitHub: github.com/yourname/sec-form4-scraper)"
    ),
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov",
}


# ----------------------------------------------------------
# Helper: choose the most recent weekday (no weekend index)
# ----------------------------------------------------------
def get_most_recent_weekday(today: date | None = None) -> date:
    if today is None:
        today = date.today()
    d = today
    # 0 = Monday, 6 = Sunday; treat 5,6 as weekend
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


# ----------------------------------------------------------
# Fetch Form 4 XML URLs from the daily index
# ----------------------------------------------------------
def fetch_form4_urls():
    d = get_most_recent_weekday()
    year = d.year
    quarter = (d.month - 1) // 3 + 1
    idx_name = f"form.{d.strftime('%Y%m%d')}.idx"
    idx_url = f"{DAILY_INDEX_BASE}/{year}/QTR{quarter}/{idx_name}"

    print(">>> Using index date:", d.isoformat())
    print(">>> Index URL:", idx_url)

    resp = requests.get(idx_url, headers=SEC_HEADERS)
    if resp.status_code != 200:
        print("!!! Failed to fetch index. HTTP status:", resp.status_code)
        print("Response snippet:", resp.text[:500])
        return []

    content = resp.text
    print("Index file length:", len(content))

    urls = []

    # The daily index is a fixed-width format after a header section.
    # Columns (approx):
    # 0-11   Form Type
    # 12-73  Company Name
    # 74-85  CIK
    # 86-97  Date Filed
    # 98-    File Name  (e.g. edgar/data/0001769628/0002058067-25-000019.txt)
    parsing = False
    for line in content.splitlines():
        # Skip until we hit the dashed separator line under the column headers
        if not parsing:
            if line.startswith("----"):
                parsing = True
            continue

        if not line.strip():
            continue

        form_type = line[0:12].strip()
        if not (form_type == "4" or form_type == "4/A"):
            continue

        company = line[12:74].strip()
        cik_raw = line[74:86].strip()
        date_filed = line[86:98].strip()
        file_name = line[98:].strip()

        # Clean CIK (drop leading zeros)
        try:
            cik_int = str(int(cik_raw))
        except ValueError:
            # In case of weird lines
            print("Skipping line with bad CIK:", line)
            continue

        # file_name example:
        #   edgar/data/0001769628/0002058067-25-000019.txt
        # accession_raw = 0002058067-25-000019
        acc_part = os.path.basename(file_name)
        accession_raw = acc_part.replace(".txt", "")
        accession_nodash = accession_raw.replace("-", "")

        xml_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_int}/{accession_nodash}/xslF345X03/doc.xml"
        )

        urls.append(xml_url)

    print(">>> Form 4 XML URLs found in index:", len(urls))
    for u in urls[:5]:
        print("   sample URL:", u)

    return urls


# ----------------------------------------------------------
# Parse each Form 4 XML
# ----------------------------------------------------------
def parse_form4(xml_url: str):
    try:
        resp = requests.get(xml_url, headers=SEC_HEADERS)
        if resp.status_code != 200:
            # Not all filings have that xslF345X03/doc.xml path; skip failures.
            # print("   Skipping (HTTP", resp.status_code, "):", xml_url)
            return None

        root = ET.fromstring(resp.text)

        issuer = root.find(".//issuer/issuerName")
        company = issuer.text if issuer is not None else ""

        reporting = root.find(".//reportingOwner")
        insider = reporting.find(".//rptOwnerName").text if reporting is not None else ""
        role_node = reporting.find(".//rptOwnerRelationship/officerTitle")
        role = role_node.text if role_node is not None else ""

        txn_nodes = root.findall(".//nonDerivativeTransaction")

        total_amount = 0.0
        shares_out = 0.0
        price_out = 0.0

        for txn in txn_nodes:
            shares_node = txn.find(".//transactionShares/value")
            price_node = txn.find(".//transactionPricePerShare/value")
            if shares_node is None or price_node is None:
                continue

            try:
                shares = float(shares_node.text)
                price = float(price_node.text)
            except (TypeError, ValueError):
                continue

            amount = shares * price
            total_amount += amount
            shares_out = shares
            price_out = price

        if total_amount >= 5_000_000:
            print(f"   ✅ BIG TRADE: {company} — {insider} — ${total_amount:,.0f}")
            return {
                "company": company,
                "ticker": "",  # TODO: lookup later
                "insider": insider,
                "role": role,
                "shares": shares_out,
                "price": price_out,
                "amount": total_amount,
                "link": xml_url,
            }
        else:
            # Uncomment to see everything:
            # print(f"   Skipping < $5M: {company} — {insider} — ${total_amount:,.0f}")
            return None

    except Exception as e:
        print("Error parsing XML for", xml_url, ":", e)
        return None


# ----------------------------------------------------------
# Write results to Google Sheet
# ----------------------------------------------------------
def write_to_sheet(rows: list[dict]):
    sheet.clear()
    sheet.append_row(
        [
            "Date",
            "Company",
            "Ticker",
            "Insider",
            "Role",
            "Shares",
            "Price",
            "Amount",
            "Link",
        ]
    )

    today_str = datetime.now().strftime("%Y-%m-%d")

    for r in rows:
        sheet.append_row(
            [
                today_str,
                r["company"],
                r["ticker"],
                r["insider"],
                r["role"],
                r["shares"],
                r["price"],
                r["amount"],
                r["link"],
            ]
        )


# ----------------------------------------------------------
# MAIN EXECUTION
# ----------------------------------------------------------
def main():
    urls = fetch_form4_urls()
    print(">>> TOTAL XML URLs TO CHECK:", len(urls))

    results = []
    for url in urls:
        parsed = parse_form4(url)
        if parsed:
            results.append(parsed)

    print(">>> Final big trades (>= $5M):", len(results))
    write_to_sheet(results)
    print("Done.")


if __name__ == "__main__":
    main()
