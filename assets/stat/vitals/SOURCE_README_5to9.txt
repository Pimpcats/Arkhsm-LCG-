ARKHAM HEALTH AND MENTAL VALUE EXTRACTIONS

CONTENTS

red_health/
  red_health_5.png
  red_health_6.png
  red_health_7.png
  red_health_8.png
  red_health_9.png

blue_mental/
  blue_mental_5.png
  blue_mental_6.png
  blue_mental_7.png
  blue_mental_8.png
  blue_mental_9.png

previews/
  health_and_mental_5_to_9_preview.png

METHOD

- Extracted directly from the five supplied 1000-pixel card images.
- No generation, reconstruction, repainting, sharpening, or enlargement.
- Original RGB pixels are preserved.
- Only the transparency boundary was processed.
- The silhouette was expanded by one source pixel before applying a
  0.45-pixel alpha feather, preventing the smoothing from shaving off
  the smallest heart vessels or brain folds.
- All detected red and blue artwork remains at 99.8–100% full opacity;
  the remaining fraction is at 253/255 alpha and is limited to the
  smoothed outermost edge.
