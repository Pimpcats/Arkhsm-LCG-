DESIGNER VERIFICATION — CONTAINS SPOILERS
2026-10-02

FINAL CANDIDATE
70 complete cells, 1319 played slots, one stable input digest:
7816c967868172384a7dcc008ea7b2cf6c5ad1fb1f8f472e427c1ad622f36b9d
No engine errors, Lua errors, table notes or missing encounter draws. Any such
trial makes the entire cell invalid; no failed trial is silently discarded.

FILES
balance-summary.json: ten played-slot aggregates, approximate intervals and carried economy.
release-results.tar.gz: every raw final trial, seed, task list and per-file hashes.
release-inputs.tar.gz: exact owned source/data/payload used by those trials.
proposal-results.tar.gz: 200 cost-screen trials and 200 opening/finale proposal trials.
paired-inputs.tar.gz: the earlier exact owned inputs shared by both proposal sets.
review-evidence.tar.gz: scoped reviewer fixtures, logs, hashes and the seeded tie probe.
structural-audit.json: effective card fronts/backs, costs, source totals and content hashes.
rules-checks.txt: current whole suite, both Lua variants and rebuilt bundle checks.
godot-verification.json / godot-log.txt: three actual rendered real-SCED emulator scenes.
render-verification.json: rebuilt changed faces and all 24 guide pages.
SHA256.json: integrity hashes of this evidence directory, excluding itself.

SCOPE AND WITHDRAWALS
The final run uses corrected Rules Reference player windows, GUID-aware encounter
draws, opening cost 2 and the finale accounting/participation/Years corrections.
Earlier early-paid-advance or missed-encounter measurements and the old 40-check
timing signoff are withdrawn. Reviewer reports retain their explicit scope/date.
The 400 valid proposal trials predate the opening asset pin and finale follow-up;
the table in FINISHING_BALANCE.md explains why their measured endpoints are useful.
They are not byte-identical final-candidate measurements.

REPRODUCE CONFIGURATION
Use Python3, pytest/reportlab/Pillow and Lua5.2/5.4. Provide the pinned external
SCED save and source below. From the repository root:

  SCED_SAVE=/absolute/path/to/save.json python3 tools/play_engine/validate_finishing.py --output .cache/finishing_rerun --workers 7
  SCED_SAVE=/absolute/path/to/save.json python3 -m pytest -q tests
  lua5.2 pipeline/lua_smoketest.lua
  lua5.4 pipeline/lua_smoketest.lua
  lua5.2 pipeline/verify_bundle.lua
  lua5.4 pipeline/verify_bundle.lua
  python3 cardforge/selftest.py

The task list records all seeds, Standard difficulty, parties and state presets.
Owned input archives preserve source snapshots even if main changes later.
INPUTS.json lists exact SHA-256 records and excluded external files. Obtain
argonui/SCED commit 0e12534a3dcaceba504f02678e999b727900f6dd; the exact save has
211 top-level objects and 2332 available player cards. External save/table bytes
are not vendored in these evidence archives and must match their recorded hashes.

SEEDS AND REPLAY
Seeds fix PRNG inputs. Lua table-order ties can select different legal paths or
actions between fresh processes and then change later draw order. Re-running a
configuration is not guaranteed to produce identical games. Raw archived trials
are the definitive measured snapshot. Same-seed proposal screens are directional,
not identical paired draws. Official Lua next/pairs references:
https://www.lua.org/manual/5.2/manual.html#pdf-next
https://www.lua.org/manual/5.4/manual.html#pdf-next

RENDER SCOPE
Godot 4.7.2/OpenGL under Xvfb rendered three 1920x1080 scenes, each limited to two
rounds. Campaign images were seeded from hash-verified local files matching
immutable asset commit edb319dc44156898bd22b8f11382d4e94e8fd485; remote HTTP
fetch of those URLs is not claimed. 200 images and the guide were independently
matched to the immutable GitHub tree. One nonvisual SCED sound/effect Unity bundle
has no mesh renderer; campaign crops and screenshots completed. Screenshots stay
gitignored because they contain campaign content. The pytest opt-in Godot test
was skipped; these actual renders are separate verification.

LIMITS
These are emulator/source/render checks, not native TTS physics, the owner's
current desktop, human playtests or exact human success probabilities. Prepared
decks are conditional budgets; carried campaigns preserve actual purchases but
stop at the first age-out without replacement investigators. Finale trials
measure contest reach and choose one eligible ending, not every ending choice or
the ending's payments/epilogue. No ordinary reset/aging/banking substitutes for
those omitted finale procedures. The requested difficulty curve remains open.
