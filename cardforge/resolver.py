"""Character resolver — name -> {lora, weight, trigger, refs, description}.

v1 ships self-contained: characters live in campaigns/<name>/characters.json.
The interface is one function so a later version can delegate to the owner's
character-select tool (Pimpcats/Character-Select-SD-and-Video) without touching
callers: swap the body, keep the signature.
"""
import json
import os


class CharacterResolver:
    def __init__(self, characters_path):
        self.characters = {}
        if os.path.exists(characters_path):
            self.characters = json.load(open(characters_path, encoding="utf-8"))

    def resolve(self, name):
        """Return the character record, or raise KeyError with a helpful message."""
        if name is None:
            return None
        if name not in self.characters:
            raise KeyError(
                "character '{}' not in characters.json (have: {})".format(
                    name, ", ".join(sorted(self.characters)) or "none"))
        return self.characters[name]

    def names(self):
        return sorted(self.characters)
