Health-heart / sanity-brain stat chits (owner-supplied art). COMPLETE 1-9.

STYLE (matches the printed cards, e.g. Guard Dog):
  white numeral, coloured outline, numeral sits INSIDE the organ shape.

STATUS - every value 1..9 has art for both organs. Nothing is drawn by code.
  1, 2   owner-supplied. Slight pale halo on the cut edge, visible against
         dark frames; re-extract with the 3-9 method if it ever matters.
  3, 4   owner-supplied. Per the owner's own notes these are NOT extracted
         from card scans - they are constructed variants built to match the
         5-9 set (same canvas and silhouette dimensions).
  5-9    owner-supplied, extracted directly from 1000px card images; original
         RGB preserved, only the alpha boundary was processed.
  See SOURCE_README_3to9.txt for the owner's full extraction method.

  An earlier inverted-style set (coloured numeral / white outline / numeral
  overflowing the organ) was wrong and has been fully replaced.

  There is NO code-drawn fallback numeral any more. _chit_numeral() was
  deleted once this set completed. If a file here goes missing the renderer
  falls back to a plain _box_text numeral, which will look obviously wrong -
  that is intentional, so a missing asset is noticed rather than disguised.

NAMING (picked up automatically, no code change needed)
  health_heart_<n>.png   n = 1..9
  sanity_brain_<n>.png   n = 1..9
  health_heart.png / sanity_brain.png = empty chits (no numeral)
