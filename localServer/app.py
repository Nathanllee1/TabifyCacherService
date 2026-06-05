# app.py
from flask import Flask, request, jsonify
import handler

app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/get")
def tabs():
    artist_name = request.args.get("artist_name")
    song_name = request.args.get("song_name")

    if not artist_name or not song_name:
        return jsonify({"error": "artist_name and song_name are required"}), 400

    try:
        return jsonify(handler.get_tabs(song_name, artist_name))
    except Exception as e:
        print("scrape failed:", repr(e))
        return jsonify({"error": "failed to fetch tab"}), 502

@app.get("/onug")
def onug():
    artist_name = request.args.get("artist")
    song_name = request.args.get("song")

    if not artist_name or not song_name:
        return jsonify({"error": "artist and song are required"}), 400

    try:
        response = jsonify(handler.is_in_ultimate_guitar(song_name, artist_name))
        response.headers["Cache-Control"] = "max-age=604800"
        return response
    except Exception as e:
        print("onug check failed:", repr(e))
        return jsonify({"error": "failed to check tab availability"}), 502
