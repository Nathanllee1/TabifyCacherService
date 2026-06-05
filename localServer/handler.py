import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import cloudscraper
from bs4 import BeautifulSoup
from curl_cffi import requests as cf_requests


SCRAPER = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)
REQUEST_TIMEOUT_SECONDS = 20
SEARCH_QUERY_SUFFIX = "chords tabs ultimate guitar"
DB_PATH = Path(
    os.environ.get("LOCALSERVER_TABS_DB", Path(__file__).with_name("tabs.sqlite3"))
)


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
    """Fetch HTML with a SQLite-backed cache around successful upstream responses."""
    cached = get_cached_response(url)
    if cached:
        return cached["body"], cached["status_code"]

    try:
        response = cf_requests.get(
            url, impersonate="chrome136", timeout=REQUEST_TIMEOUT_SECONDS
        )
        html, status_code = response.text, response.status_code
    except Exception:
        response = SCRAPER.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        html, status_code = response.text, response.status_code

    cache_response(url, status_code, html)
    return html, status_code


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS http_cache (
            cache_key TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn


def get_cached_response(url):
    with get_db() as conn:
        row = conn.execute(
            "SELECT status_code, body FROM http_cache WHERE cache_key = ?",
            (url,),
        ).fetchone()
    return dict(row) if row else None


def cache_response(url, status_code, body):
    if status_code != 200 or not body:
        return

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO http_cache (cache_key, url, status_code, body)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                url = excluded.url,
                status_code = excluded.status_code,
                body = excluded.body,
                updated_at = CURRENT_TIMESTAMP
            """,
            (url, url, status_code, body),
        )


def get_tab_page_urls(search_url):
    """Given search url, gets the url of the correct tab page."""
    html, status_code = fetch_html(search_url)
    print(search_url, status_code)

    if status_code != 200:
        return []

    soup = BeautifulSoup(html, "html.parser")
    data_store = soup.find(class_="js-store")
    if not data_store or "data-content" not in data_store.attrs:
        return []

    try:
        page_data = json.loads(data_store["data-content"])
    except json.JSONDecodeError:
        return []

    results = (
        page_data.get("store", {})
        .get("page", {})
        .get("data", {})
        .get("results", [])
    )
    return list(dict.fromkeys(
        tab["tab_url"]
        for tab in results
        if tab.get("type") == "Chords"
        and tab.get("tab_url", "").startswith(
            "https://tabs.ultimate-guitar.com/tab/"
        )
    ))


def get_tab_page_urls_ddg(song_name, artist_name):
    """Resolve tab URLs via DuckDuckGo results to avoid UG search anti-bot blocks."""
    search_url = build_duckduckgo_url(song_name, artist_name)
    html, status_code = fetch_html(search_url)
    print(search_url, status_code)

    if status_code != 200:
        return []

    tabs = []
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
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
    tab_page_urls = get_tab_page_urls(build_search_url(song_name, artist_name))
    if not tab_page_urls:
        tab_page_urls = get_tab_page_urls_ddg(song_name, artist_name)

    tab_page_urls = tab_page_urls[:6] # limit to 6 songs
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
