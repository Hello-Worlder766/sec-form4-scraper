def fetch_recent_form4s_json():
    """
    Pulls ALL Form 4 filings from the past 14 days using SEC's master
    filings index (submissions feed). This does not rely on the broken
    "latest filings" endpoint.
    """

    print(">>> Fetching master index for all companies (14 days)…")

    base = "https://data.sec.gov/submissions/"

    # Master CIK list endpoint (documented)
    CIK_LIST_URL = "https://www.sec.gov/files/company_tickers.json"

    try:
        company_data = requests.get(CIK_LIST_URL, headers=HEADERS).json()
    except Exception as e:
        print("Error downloading CIK list:", e)
        return []

    urls = []
    count = 0

    # Go through every company in the SEC database
    for entry in company_data.values():
        cik = str(entry["cik_str"]).zfill(10)

        filings_url = f"{base}CIK{cik}.json"

        try:
            data = requests.get(filings_url, headers=HEADERS).json()
        except:
            continue

        if "filings" not in data or "recent" not in data["filings"]:
            continue

        recent = data["filings"]["recent"]

        forms = recent.get("form", [])
        accession = recent.get("accessionNumber", [])
        report_dates = recent.get("filingDate", [])

        # Loop through all recent filings for this company
        for f, acc, date in zip(forms, accession, report_dates):

            # Only Form 4s
            if f != "4":
                continue

            # Filter filings to last 14 days
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
                if (datetime.now() - dt).days > 14:
                    continue
            except:
                continue

            acc_clean = acc.replace("-", "")

            xml_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{acc_clean}/xslF345X03/doc.xml"
            )

            urls.append(xml_url)
            count += 1

        # Limit (optional) to speed up testing
        if count > 300:
            break

    print(">>> Found Form 4 XML URLs (14 days):", len(urls))
    return urls
