# Card frame templates (drop-in)

Put the official-style frame graphics here — the borders, parchment boxes,
class banners, stat plates: everything on a card EXCEPT illustration and text.

Where to get them (best first):
1. **Strange Eons Arkham LCG plugin** — contains the exact frames for every
   card type/class. Install it in SE (Toolbox > Manage Plug-ins > Catalog),
   locate the plugin bundle in your SE plug-ins folder, then:
       python3 tools/extract_se_frames.py <plugin file> --list
       python3 tools/extract_se_frames.py <plugin file> --filter investigator
2. **Hi-res blank templates** — the BGG thread "Hi-res blank templates for
   custom investigator cards" distributes exactly this: full frames with an
   empty art window and empty text areas.
3. **Mythos Busters Discord / the Barnaby Files guide** — community template
   packs and the AH font pack (the glyph font is already vendored in
   assets/fonts/).

Once real frames land here, the placeholder renderer can composite onto them
(frame + illustration + print-layer text = near-final cards without SE) — that
overlay calibration is a one-pass job once the images exist to measure.

Scope (per the owner): strictly fan content — free, online only, for the
community and the owner's own group. No printing, no sale. That matches the
long-standing SCED/fan-content norms these community assets exist under; the
folder stays gitignored (README excepted) so the frames travel by download, not
by this repo.
