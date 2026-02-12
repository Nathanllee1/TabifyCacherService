from http.server import BaseHTTPRequestHandler
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs


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

def get_tab_page_urls(search_url):
    """Given search url, gets the url of the correct tab page."""
    resp = requests.get(search_url)
    soup = BeautifulSoup(resp.content, "html.parser")
    soup = soup.find(class_="js-store")
    
    print(search_url, resp)
    
    page_data = json.loads(soup["data-content"])
    results = page_data["store"]["page"]["data"]["results"]
    tabs = []
    for tab in results:
        if "type" in tab.keys() and tab["type"] == "Chords":
            tabs.append(tab["tab_url"])
    return tabs


def scrape_tab_html(tab_page_url):
    """Given the url of the tab page, returns the HTML of the actual tab."""
    resp = requests.get(tab_page_url)
    soup = BeautifulSoup(resp.content, "html.parser")
    soup = soup.find(class_="js-store")
    page_data = json.loads(soup["data-content"])
    unparsed_html = page_data["store"]["page"]["data"]["tab_view"]["wiki_tab"]["content"]
    return parse_tab_page(unparsed_html)


def get_tabs(song_name, artist_name):
    """Returns the tab for a given song.
    Args:
            song_name (string): The name of the song whose tab will be scraped.
            artist_name (string): The name of the song's artist.
    Returns:
            string: The HTML of the tab.
    """
    search_url = build_search_url(song_name, artist_name)
    tab_page_urls = get_tab_page_urls(search_url)[:6] # limit to 6 songs
    results = []
    for url in tab_page_urls:
        results.append({
            "chords": scrape_tab_html(url),
            "url": url
        })

    return results


def main(event, context):
    print(event)
    arguments = parse_qs(event["rawQueryString"])

    artist_name = arguments["artist_name"][0]
    song_name = arguments["song_name"][0]

    content = get_tabs(song_name, artist_name)

    return content
