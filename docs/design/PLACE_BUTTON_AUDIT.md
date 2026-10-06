# Place button audit (2026-10-06)

Question: is the scenario box's Place button built the way SCED builds it?

## Findings

| Part | SCED | The Still Hour |
|---|---|---|
| Campaign box script | MemoryBag module | src/tts/memory_bag.lua. Code body identical to argonui/SCED main (src/MemoryBag.ttslua) today; only our 7-line header comment differs |
| Scenario box script | the same MemoryBag module | **our own** src/tts/loop_box.lua |
| Button layout and position math | generateButtonData() | copied from it |
| State format | LuaScriptState {"ml": {guid: {pos, rot, lock}}} | the same |
| What Place does | `self.takeObject` per remembered object, in one loop: objects leave the bag and keep their GUIDs | `spawnObjectData` per contained object: a deep copy of its data with **new random GUIDs and tags**; the bag keeps its contents (so the box can be laid out again each loop) |
| After Place | nothing | 2 seconds later calls shApiSyncBoard on the control token: Board.syncAll over every location card, Dissonance.syncBag (chaos bag), refreshControl |

So the answer is "partly": the campaign box and the button look and state are
SCED's, but scenario Place is a different mechanism. The difference exists for
a reason (loops need a fresh copy every time, and SCED's bag empties).

## What was ruled out here

- Size: The First Hour box (8 top-level, 38 nested objects, 54 KB of data) is
  smaller than the real One Last Job box (13 top-level, 63 nested, 76 KB).
  The Square is the same size (75 KB) as it.
- Images: 43 images, 6.6 MB download, about 133 MB decoded, all 750x1050 or
  1050x750 JPEGs, the same dimensions SCED uses.
- The data itself: no Lua on any contained object; identical object shapes.

## What is still unknown

Which of the three differences crashes TTS cannot be told from here (the
emulator does not reproduce it). Suspects: spawning ~40 objects with nested
decks in one frame via spawnObjectData; the 6-hex-digit GUIDs from an unseeded
math.random (collisions across boxes or repeats); the board sync firing 2
seconds later while images are still loading.

## Planned (no code changed yet)

1. Step logging before each action, so Player.log names the last thing run.
2. Spawn a few objects at a time (Wait.frames between batches) and run the board
   sync from the last spawn's callback instead of a fixed 2 seconds.
3. Seed the GUID generator and check each GUID against the table before use.
4. If it still crashes: a variant box that uses SCED's exact takeObject Place
   for first use, to separate "our spawn method" from "our data".

Needed from the owner: the last 60 lines of Player.log after the crash, and
whether Place on The Lighthouse box also crashes.
