import requests
from bs4 import BeautifulSoup as BS


def extract_links_for_year(year: int):
    print(f"Extracting links for {year}")
    url = f"https://www.mcmillenandwife.com/steelers_{year}_season.html"
    response = requests.get(url)

    soup = BS(response.text, "html.parser")
    anchors = soup.find_all("a", href=True)

    matching_hrefs = set()
    for anchor in anchors:
        raw_href = anchor.get("href")

        if not raw_href:
            print("href attribute is falsey. Skipping.")
            continue

        to_match = raw_href.strip()
        if to_match.startswith(f"{year}_Steelers"):
            matching_hrefs.add(to_match)

    return matching_hrefs
