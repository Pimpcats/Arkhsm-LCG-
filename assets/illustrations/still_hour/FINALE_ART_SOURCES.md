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
| sthr-res-7 | sthr-loc-square | 0, 120 | sepia (0.75) |
| sthr-res-8 | sthr-loc-square | 228, 200 | cold (0.85) |
