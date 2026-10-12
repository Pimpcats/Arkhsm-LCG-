# Finale boss art (2026-10-11, provisional)

No image-generation service is reachable from the build environment, so the seven finale cards added for the
three-period boss fight use detail crops (1080 x 720 from 1536 x 1024, scaled back) of approved illustrations,
toned per period: sepia for the Past, cold grey-blue for the Future, full colour for the Present. The scenes in
pipeline/build_art_manifest.py are the briefs for painted replacements; replace any of these with a newly painted
illustration of the same id when one is made.

| Card | Source illustration | Crop origin (x, y) | Tone |
|---|---|---|---|
| sthr-loc-firstoccultation | sthr-loc-hubsquare | 300, 150 | sepia |
| sthr-loc-morningafter | sthr-appointed-approach | 228, 150 | cold |
| sthr-form-past | sthr-appointed | 228, 120 | sepia |
| sthr-form-future | sthr-appointed | 100, 260 | cold |
| sthr-form-present | sthr-appointed | 380, 200 | full colour, +15% contrast |

## Late objectives (act 3a, 2026-10-12, provisional)

Portrait crops (768 x 1152, scaled to 1024 x 1536) of the matching approved act illustrations, with a pale dawn
wash (35%) that marks the late acts. Briefs are in pipeline/build_art_manifest.py.

| Card | Source illustration | Crop origin (x, y) |
|---|---|---|
| sthr-act-keeplight | sthr-act-lamp | 128, 0 |
| sthr-act-truehour | sthr-act-whythirteen | 256, 192 |
| sthr-act-lastmilestone | sthr-act-walkbackward | 0, 384 |
| sthr-act-calltheroll | sthr-act-vote | 256, 300 |
| sthr-act-stopwheel | sthr-act-wheelturns | 128, 96 |

## Painted (ChatGPT, 2026-10-12)

Replaced their stand-in crops: Set the Hour Right (pack #140, cut to portrait from the landscape image), Stranded
Before (#153) and Stranded After (#154), both trimmed of the cut line and fitted to the story window.
