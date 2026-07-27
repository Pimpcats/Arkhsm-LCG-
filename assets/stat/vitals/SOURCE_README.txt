Health-heart / sanity-brain stat chits (owner-supplied art).

CORRECT STYLE (what the printed cards use, e.g. Guard Dog):
  white numeral, coloured outline, numeral sits INSIDE the organ shape.

STATUS
  1, 2   owner-supplied, correct style. Slight pale halo on the cut edge.
  3      NOT SUPPLIED. An earlier file was pulled for colour fringing.
  4      NOT SUPPLIED. Never existed.
  5-9    owner-supplied, correct style, cleanly cut (see
         SOURCE_README_5to9.txt for the extraction method). These REPLACED an
         earlier inverted-style set (coloured numeral / white outline /
         numeral overflowing the organ), which was wrong and is gone.

  Values 3 and 4 have no art, so they fall back to the empty chit plus a
  numeral drawn in Bolton by _chit_numeral() in
  pipeline/render_placeholders.py. That numeral is NOT owner art - it is a
  visibly-different stand-in. DELETE _chit_numeral and its two call sites
  once 3 and 4 are supplied.

NAMING (picked up automatically, no code change needed)
  health_heart_<n>.png   n = 1..9
  sanity_brain_<n>.png   n = 1..9
  health_heart.png / sanity_brain.png = empty chits (no numeral)
