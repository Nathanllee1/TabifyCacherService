import hashlib
import json
import secrets
from datetime import datetime, timezone
from urllib.parse import parse_qs

import requests


REQUEST_TIMEOUT_SECONDS = 20
UG_API_BASE_URL = "https://api.ultimate-guitar.com/api/v1"
UG_CLIENT_ID = secrets.token_hex(8)
UG_USER_AGENT = "UGT_ANDROID/4.11.1 (Pixel; 8.1.0)"


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


def build_ug_api_key(now=None):
    """Generate the hourly request signature expected by UG's mobile API."""
    now = now or datetime.now(timezone.utc)
    payload = f"{UG_CLIENT_ID}{now.strftime('%Y-%m-%d')}:{now.hour}createLog()"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def fetch_ug_json(path, params):
    headers = {
        "Accept": "application/json",
        "Accept-Charset": "utf-8",
        "User-Agent": UG_USER_AGENT,
        "X-UG-CLIENT-ID": UG_CLIENT_ID,
        "X-UG-API-KEY": build_ug_api_key(),
    }

    try:
        response = requests.get(
            f"{UG_API_BASE_URL}{path}",
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, json.JSONDecodeError) as error:
        print({"source": "ultimate-guitar-api", "path": path, "error": str(error)})
        return {}


def search_tabs(song_name, artist_name):
    data = fetch_ug_json(
        "/tab/search",
        [
            ("title", f"{artist_name} {song_name}"),
            ("page", 1),
            ("type[]", 300),
        ],
    )
    return [
        tab
        for tab in data.get("tabs", [])
        if tab.get("type") == "Chords" and tab.get("status") == "approved"
    ]


def fetch_tab(tab):
    return fetch_ug_json(
        "/tab/info",
        {
            "tab_id": tab["id"],
            "tab_access_type": tab.get("tab_access_type", "public"),
        },
    )


def get_tabs(song_name, artist_name):
    """Returns the tab for a given song.
    Args:
            song_name (string): The name of the song whose tab will be scraped.
            artist_name (string): The name of the song's artist.
    Returns:
            string: The HTML of the tab.
    """
    results = []
    for tab in search_tabs(song_name, artist_name)[:6]:
        tab_data = fetch_tab(tab)
        content = tab_data.get("content", "")
        url = tab_data.get("urlWeb", "")
        if not content or not url:
            continue
        results.append({
            "chords": parse_tab_page(content),
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
