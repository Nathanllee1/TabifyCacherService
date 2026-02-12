import json
import cloudscraper
import re
from bs4 import BeautifulSoup
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from curl_cffi import requests as cf_requests


SCRAPER = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)
REQUEST_TIMEOUT_SECONDS = 20
SEARCH_QUERY_SUFFIX = "chords tabs ultimate guitar"


def build_chord(chord):
    return f'<span class="_3PpPJ OrSDI" data-name="{chord}" style="color: rgb(0, 0, 0);">{chord}</span>'


def get_chord_type(unparsed_html, index):
    characters_in_chord = 10
    chord_type = unparsed_html[index+4]
    index = index + 5
    while unparsed_html[index] != "[":
        chord_type += unparsed_html[index]
        characters_in_chord += 1
        index += 1
    return chord_type, characters_in_chord


def char_is_chord(unparsed_html, index):
    return unparsed_html[index:index+4] == "[ch]"


def parse_tab_page(unparsed_html):
    tab_html = '<section class="_3cXAr _1G5k-"><code class="_3enQP"><pre class="_3F2CP _3hukP" style="font-size: 13px; font-family: Roboto Mono, Courier New, monospace;"><span class="_3rlxz">'
    i = 0
    while i < len(unparsed_html):
        # If carriage return ...
        if unparsed_html[i:i+2] == "\r":
            i += 2
        # If newline ...
        elif unparsed_html[i:i+2] == "\n":
            tab_html += "\n"
            i += 2
        # Below statements are added to skip the tab tags
        elif unparsed_html[i:i+6] == "[/tab]":
            i += 6
        elif unparsed_html[i:i+5] == "[tab]":
            i += 5
        # If the next section is a chord ...
        elif char_is_chord(unparsed_html, i):
            chord_type, chars = get_chord_type(unparsed_html, i)
            tab_html += build_chord(chord_type)
            i += chars
        # If character isn't special, add it normally
        else:
            tab_html += unparsed_html[i]
            i += 1
    tab_html += "</section>"
    return tab_html


def build_search_url(song_name, artist_name):
    """Builds the Search URL from the artist and song names."""
    fixed_name = artist_name.replace("&", "%26")
    fixed_song = song_name.replace("&", "%26")
    return f"https://www.ultimate-guitar.com/search.php?title={fixed_name} {fixed_song}&page=1&type=300".replace(" ", "%20")

def build_duckduckgo_url(song_name, artist_name):
    query = f"{artist_name} {song_name} {SEARCH_QUERY_SUFFIX}"
    return f"https://duckduckgo.com/html/?q={quote_plus(query)}"

def fetch_html(url):
    """Use browser impersonation first. Fallback to cloudscraper for compatibility."""
    try:
        response = cf_requests.get(
            url, impersonate="chrome136", timeout=REQUEST_TIMEOUT_SECONDS
        )
        return response.text, response.status_code
    except Exception:
        response = SCRAPER.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        return response.text, response.status_code

def get_tab_page_urls(song_name, artist_name):
    """Resolve tab URLs via DuckDuckGo results to avoid UG search anti-bot blocks."""
    search_url = build_duckduckgo_url(song_name, artist_name)
    html, status_code = fetch_html(search_url)
    print(search_url, status_code)

    if status_code != 200:
        return []

    hrefs = re.findall(r'href="([^"]+)"', html)
    tabs = []
    for href in hrefs:
        if "uddg=" in href:
            parsed = parse_qs(urlparse(href).query)
            candidate = unquote(parsed.get("uddg", [""])[0])
        else:
            candidate = href

        if (
            candidate.startswith("https://tabs.ultimate-guitar.com/tab/")
            and "-chords-" in candidate
            and candidate not in tabs
        ):
            tabs.append(candidate)

    return tabs


def scrape_tab_html(tab_page_url):
    """Given the url of the tab page, returns the HTML of the actual tab."""
    html, status_code = fetch_html(tab_page_url)
    if status_code != 200:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    soup = soup.find(class_="js-store")

    if not soup or "data-content" not in soup.attrs:
        return ""

    page_data = json.loads(soup["data-content"])
    unparsed_html = (
        page_data.get("store", {})
        .get("page", {})
        .get("data", {})
        .get("tab_view", {})
        .get("wiki_tab", {})
        .get("content", "")
    )
    if not unparsed_html:
        return ""

    return parse_tab_page(unparsed_html)


def get_tabs(song_name, artist_name):
    """Returns the tab for a given song.
    Args:
            song_name (string): The name of the song whose tab will be scraped.
            artist_name (string): The name of the song's artist.
    Returns:
            string: The HTML of the tab.
    """
    tab_page_urls = get_tab_page_urls(song_name, artist_name)[:6] # limit to 6 songs
    results = []
    for url in tab_page_urls:
        parsed_tab = scrape_tab_html(url)
        if not parsed_tab:
            continue
        results.append({
            "chords": parsed_tab,
            "url": url
        })

    return results


def main(event, context):
    print(event)
    arguments = parse_qs(event.get("rawQueryString", ""))

    if "artist_name" not in arguments or "song_name" not in arguments:
        return []

    artist_name = arguments["artist_name"][0]
    song_name = arguments["song_name"][0]

    content = get_tabs(song_name, artist_name)

    return content
