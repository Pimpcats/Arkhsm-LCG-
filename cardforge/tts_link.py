"""Live link to a RUNNING Tabletop Simulator — one-click card drops.

TTS ships an External Editor API: while a game is loaded it listens on
localhost:39999 for JSON messages from editors; messageID 3 executes a Lua
snippet in the live game's Global context. We use exactly that to
spawnObjectJSON() a finished card onto the table the owner is looking at —
no save reload, no file copying, the card just appears.

Works with ANY SCED/Arkham mod version (and vanilla TTS): spawnObjectJSON is
a base-game API, and the object we send is the same schema-aligned card the
mod build produces. TTS only needs to be OPEN with any game loaded.
"""
import json
import os
import socket
import sys

from . import runner

TTS_HOST, TTS_PORT = "127.0.0.1", 39999


def send_lua(script, timeout=4):
    """Execute a Lua snippet in the running TTS game (External Editor API,
    messageID 3). Raises ConnectionError-family if TTS isn't listening."""
    msg = json.dumps({"messageID": 3, "guid": "-1", "script": script})
    with socket.create_connection((TTS_HOST, TTS_PORT), timeout=timeout) as s:
        s.sendall(msg.encode("utf-8"))
    return True


def card_object(card_id, campaign="still_hour"):
    """The card's full TTS object (same generator as the mod build), with the
    CURRENT composed face/back wired in as local file:/// URLs."""
    sys.path.insert(0, os.path.join(runner.repo_root(), "pipeline"))
    import build_cards
    specs = []
    for f in ("stillhour_cards_spec.json", "stillhour_encounter_spec.json"):
        p = os.path.join(runner.repo_root(), "pipeline", f)
        if os.path.exists(p):
            specs += json.load(open(p, encoding="utf-8"))
    spec = next((c for c in specs if c["id"] == card_id), None)
    if spec is None:
        raise KeyError("no card with id " + card_id)
    obj = build_cards.build_card(spec)
    faces = os.path.join(runner.repo_root(), "art", "faces")

    def file_url(name):
        p = os.path.join(faces, name)
        return "file:///" + p.replace(os.sep, "/").lstrip("/") \
            if os.path.exists(p) else None
    deck_id = list(obj["CustomDeck"])[0]
    face = file_url(card_id + ".png")
    back = file_url(card_id + "-back.png")
    if face:
        obj["CustomDeck"][deck_id]["FaceURL"] = face
    if back:
        obj["CustomDeck"][deck_id]["BackURL"] = back
    return obj


def spawn_card(card_id, campaign="still_hour"):
    """Drop the card onto the live table, a hand-height above the center."""
    obj = card_object(card_id, campaign)
    lua = ("spawnObjectJSON({{json = [==[{}]==], position = {{0, 3, 0}}}})\n"
           "broadcastToAll('CardForge: {} dropped in', {{0.85, 0.65, 0.28}})"
           .format(json.dumps(obj), obj.get("Nickname", card_id)))
    send_lua(lua)
    return obj.get("Nickname", card_id)
