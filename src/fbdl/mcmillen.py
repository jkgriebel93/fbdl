import requests
import time
from bs4 import BeautifulSoup as BS

import sys

_, input_year = sys.argv


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


# https://www.mcmillenandwife.com/1991_Steelers_26_vs_Chargers_20.html
if __name__ == "__main__":
    # for input_year in range(1976, 1990):
    partial_links = extract_links_for_year(input_year)
    full_links = [f"https://www.mcmillenandwife.com/{link}\n" for link in partial_links]

    with open(f"{input_year}/{input_year}_games.txt", "w") as outfile:
        outfile.writelines(full_links)
    print(f"Completed extraction for {input_year}. Pausing for 10 seconds.")
    time.sleep(10)
