# app.py
from flask import Flask, request, jsonify
from handler import get_tabs

app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/tabs")
def tabs():
    artist_name = request.args.get("artist_name")
    song_name = request.args.get("song_name")

    if not artist_name or not song_name:
        return jsonify({"error": "artist_name and song_name are required"}), 400

    try:
        return jsonify(get_tabs(song_name, artist_name))
    except Exception as e:
        print("scrape failed:", repr(e))
        return jsonify({"error": "failed to fetch tab"}), 502