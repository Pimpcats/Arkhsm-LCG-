# Assistant campaign workflow

## Owner experience

The assistant produces the campaign end to end. The owner reviews selected art
under neutral labels, then receives a playable package and short loading steps.
Keep plot, card effects, encounter identities and outcomes out of those steps.
Default to preserving the existing campaign design and correcting implementation
gaps. Do not treat old BUILD_STATUS notes as current without checking code/data.

## Connection and boundaries

GitHub is the shared handoff. This module adds no public server and requires no
API key to register artwork generated in chat. It is not a remote desktop link,
MCP server, unattended agent, or a connection to the owner's localhost.
The assistant runs these commands in its checkout whenever possible; they are
not a homework checklist for the owner. A local checkout needs the branch and
assets pulled before its Studio can use the results.

## Read the current campaign

    python -m cardforge.assistant_bridge --campaign still_hour export --output /tmp/campaign-context.json

This exports effective card specs with editor overrides, scenario assignments,
character references and art jobs. It deliberately excludes backend credentials.
The output CONTAINS SPOILERS: assistant context only, never an art-review handout.
Read the design guide and change orders too; the export does not replace them.
Cards without jobs include text-only cards and missing briefs; resolve those
before claiming complete art coverage. Registered art still needs visual review.

## Author content

Use the existing campaign feed schema in docs/design/CAMPAIGN_FEED.md. Keep
scenario manifests, card specifications, overrides and assignments consistent.
Use the editor's existing import path when running Studio. Preserve existing
edits and stable IDs, and validate all setup, map and resolution references.
Never upload unfinished spoiler-bearing material as an owner-facing review.

## Generate and assemble art

Use the available image-generation tool with the campaign brief, approved visual
references, character descriptions and individual scene context. Generate raw
illustrations without card frames or rules text. The deterministic renderer adds
those. Recurring characters need reference-image continuity; a name in a prompt
alone is not sufficient. Keep a stable art direction across locations and cards.

    python -m cardforge.assistant_bridge --campaign still_hour register-art --card CARD_ID --image /path/to/generated.png
    python -m cardforge.assistant_bridge --campaign still_hour sync-art

Registration validates and converts the image, saves a content-addressed PNG
under campaigns/still_hour/assistant/art/, and records its hash in art.json.
Commit those files so artwork survives sessions and reaches the desktop checkout.
Sync checks hashes before changing selections, then writes the existing
chosen.txt and index.json formats. Existing unrelated selections are preserved.
It does not mark the backend generation ledger complete or silently render cards.
Run the existing renderer after sync:

    python pipeline/render_placeholders.py

Use the existing compiler/export workflow after checking scenario readiness.
Do not force readiness locks to manufacture a successful build. Keep build and
playtest evidence separate; desktop TTS execution requires a reachable TTS host.

## Finish and resume

Update campaigns/still_hour/assistant/production.json with the completed stage,
next actions and validation evidence. Never put credentials in it. On subsequent
requests, inspect current repository state and resume from evidence, not an old
conversation summary. Deliver a tested package when ready; clearly distinguish
offline validation from actual playtesting.
