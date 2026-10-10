# Quest card art (2026-10-10)

No image-generation service is reachable from the build environment, so the ten personal quest cards
use detail crops (1080 x 720 from 1536 x 1024, scaled back to 1536 x 1024) of already approved
illustrations whose subject matches the card's scene in pipeline/art_manifest.json. Each pair (quest
and unlocked card) shares a source, as the manifest's "the same ..." scenes do. Story assets were
avoided so that no quest card shows a later reveal. Replace any of these with a newly painted
illustration of the same id when one is made.

| Card | Source illustration | Crop origin (x, y) |
|---|---|---|
| sthr-quest-elias | sthr-loc-keepersquarters | 456, 230 |
| sthr-questdone-elias | sthr-loc-lanternroom | 228, 60 |
| sthr-quest-ayako | sthr-loc-readingroom | 0, 200 |
| sthr-questdone-ayako | sthr-loc-readingroom | 456, 304 |
| sthr-quest-cass | sthr-markeddeck | 200, 180 |
| sthr-questdone-cass | sthr-seenthishand | 330, 40 |
| sthr-quest-seraphine | sthr-bell | 240, 40 |
| sthr-questdone-seraphine | sthr-bell | 456, 280 |
| sthr-quest-birdie | sthr-loc-milestones | 228, 200 |
| sthr-questdone-birdie | sthr-loc-turning | 228, 150 |
