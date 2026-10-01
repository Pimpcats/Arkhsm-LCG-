# Making a new campaign — owner quickstart

You bring the idea; the assistant does the writing, rules, cards, guide, balance,
testing and packaging the same way The Still Hour was made. You make a handful
of calls and then play it as a first-time player. No spoilers reach you in chat.

## Start one

Open a Claude Code session on this repository (web or app) and type:

> /new-campaign Theme: … Tone: … Players: … Length (scenarios): … Must have / never: …

Anything you leave out gets a sensible default (3 players, 8 scenarios, the
Arkham painted art style, the win-rate curve below).

**Resume later:** `/new-campaign continue <name>`. The assistant picks up from
the campaign's production tracker, not from memory.

## Your checkpoints (everything else is automatic)

| # | When | What you do | Time |
|---|---|---|---|
| 1 | Start | Give the brief above | 2 min |
| 2 | Pitch | Pick one of 2–3 spoiler-free pitches | 2 min |
| 3 | Difficulty | Confirm the win-rate curve (default: early 80%, then 70 / 60 / 50, finale 40% at 3 players; never above 80%) | 1 min |
| 4 | Art direction | Approve the look (default: the same painted Arkham style as The Still Hour) | 2 min |
| 5 | Art | Generate the images from the prompt pack (separate track, below) and review them under neutral labels | your pace |
| 6 | Play | Load the saved object in Tabletop Simulator (docs/LOADING.md) | 5 min |

You are only asked when a choice is genuinely yours. You never write content,
name files or maintain lists.

## What the assistant does between checkpoints

1. **Design** (spoiler file): structure, core mechanic, story branches that echo
   into the finale, campaign log, chaos-bag changes, XP plan.
2. **Rules and cards** in official templating, with three independent wording
   passes.
3. **Official comparison** (`tools/official_compare/compare.py`) against 54
   official scenarios: doom, act and location clues, map connections, enemies
   and elites, encounter-card mix, chaos-bag changes, XP. Gaps are reported to
   you as numbers, fixed if they are real.
4. **Balance**: computer-played games (the play engine) tuned to your
   curve, reported to you **by scenario number**, numbers only.
5. **Build and test**: cards rendered in the official frames, guide PDF, campaign
   log, Control token, the full test suites, then publish.
6. **Deliver**: one saved object to load, plus anything you need to know that
   isn't a spoiler.

Every report says honestly what was checked: computer-played games and test
suites are not a human playtest.

## The art track (separate)

The art is generated outside the build, in the house style already used for The
Still Hour (1920s painted pulp illustration, restrained palette, no lettering).
The assistant writes the scene for every card and produces a **prompt pack**
(`campaigns/<id>/art/ART_PACK.md`): one request per ChatGPT chat, up to four
images each, style included, each image numbered. You run the chats, save the
images by number, and the assistant imports, frames and reviews them. Cards
play fine with placeholder art until then, so art never blocks testing or play.

## Which machine

Nothing runs on your PC except Tabletop Simulator. The assistant works in its
own cloud checkout and pushes to GitHub; you download the saved object. The
only local step is copying that file into
`Documents\My Games\Tabletop Simulator\Saves\Saved Objects\` (Windows File
Explorer), as in docs/LOADING.md.
