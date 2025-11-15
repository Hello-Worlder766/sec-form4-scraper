import requests
import re
import time
from datetime import datetime, timedelta

RSS_URL = "https://www.sec.gov/cgi-bin/current?q1=4&q2=0"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; InsideSignalTrader; "
        "+https://github.com/Hello-Worlder766/sec-form4-scraper; "
        "email=nathanrcook766@gmail.com)"
    )
}

def fetch_sec_page():
    """Fetch SEC page with retries if blocked by 'undeclared automated tool'."""
    for attempt in range(5):
        resp = requests.get(RSS_URL, headers=HEADERS)
        text = resp.text

        # If SEC blocks us, the HTML contains the exact line you saw
        if "Your Request Originates from an Undeclared Automated Tool" in text:
            print(f"⚠ SEC blocked us (attempt {attempt+1}/5). Waiting 10 seconds and retrying...")
            time.sleep(10)
            continue

        return text

    raise RuntimeError("SEC blocked all attempts — update User-Agent or slow schedule")


def fetch_form4_urls():
    html = fetch_sec_page()

    print("Fetched SEC page length:", len(html))

    # Real Form 4 pattern on the human-readable feed
    pattern = re.compile(
        r"Accession Number:\s+([0-9\-]+)",
        re.MULTILINE
    )

    matches = pattern.findall(html)
    print("Matches found:", len(matches))

    # Build URLs
    urls = [
        f"https://www.sec.gov/Archives/edgar/data/{acc.replace('-', '')}/{acc}/xslF345X04/doc.xml"
        for acc in matches
    ]

    return urls


def main():
    print("=== Fetching URLs ===")
    urls = fetch_form4_urls()
    print("Found URLs:", len(urls))

    print("Done.")


if __name__ == "__main__":
    main()
