# CardForge Studio — header banner (Krea request)

Ready to paste into Krea. Target file: **`assets/branding/banner.png`**, **2048 × 512**
(4:1). Overwrite the placeholder that ships in that folder; the app serves it
behind the header automatically (`/art?p=assets/branding/banner.png`).

The header lays a graded dark overlay on top — near-opaque at the left (title)
and right (buttons), lighter across the middle — so **keep the focal art centred**
and expect the outer thirds to sit under text. Low, moody contrast reads best;
a busy or bright banner fights the UI.

## Size / framing
- 2048 × 512, horizontal. Safe focal zone: the centre ~1100 px.
- Leave the far left (~360 px) and far right (~520 px) quiet — they carry the
  wordmark and the action buttons.

## Style block (paste as the prompt)
> Cinematic Lovecraftian horror banner, a drowned New England coast at the still
> hour before dawn: fog over black water, a half-sunk clocktower, faint bioluminescent
> tide, an immense unseen presence suggested by silhouette and ripple rather than
> shown. Muted teal-and-ash palette, deep shadow, cold moonlight, film grain, painterly
> matte-painting finish, wide panoramic composition, negative space across the middle,
> ominous and quiet, no text.

## Negative block
> text, letters, watermark, signature, logo, UI, frame, border, bright saturated
> colours, cartoon, cute, high-key lighting, busy clutter, faces in close-up, gore,
> modern objects, lens flare, oversharpened.

## Five scenes to try (pick the one that reads under the overlay)
1. **Drowned clocktower** — a leaning, half-submerged tower at centre, its clock
   face a pale disc; fog banks; the tide glinting faint green.
2. **The watcher offshore** — flat black sea, a vast low silhouette on the horizon,
   only its outline and the water it displaces visible; gulls scattering.
3. **Tide of eyes** — bioluminescent shapes under dark water forming a slow spiral,
   suggesting something looking up; jetty pilings in silhouette.
4. **The still hour street** — a fog-choked coastal lane, gas lamps guttering, long
   shadows, a single lit upstairs window; dread, no figures.
5. **Beneath the surface** — looking up from underwater toward a pale broken moon,
   kelp and tentacular silhouettes at the edges, light shafts through the murk.

## Selection rule
Generate 3–4 per scene. Choose the frame that:
- keeps its interest in the **centre third** (the outer thirds vanish under the overlay),
- stays **dark enough** that white header text stays legible on top,
- reads as atmosphere, not a literal monster portrait — a suggestion beats a reveal.

Export at 2048 × 512 (crop/outpaint to fit), save as `assets/branding/banner.png`,
reload the app. If it's too bright once placed, either dim the export or raise the
overlay opacity in the `header{…}` rule (`cardforge/studio.py`).

## Favicon
`assets/branding/cardforge.ico` now ships a real multi-size icon (a pale ringed
eye). Replace it too if the banner suggests a stronger mark.
