ARKHAM HEALTH AND MENTAL VALUE EXTRACTIONS

CONTENTS

red_health/
  red_health_3.png
  red_health_4.png
  red_health_5.png
  red_health_6.png
  red_health_7.png
  red_health_8.png
  red_health_9.png

blue_mental/
  blue_mental_3.png
  blue_mental_4.png
  blue_mental_5.png
  blue_mental_6.png
  blue_mental_7.png
  blue_mental_8.png
  blue_mental_9.png

previews/
  health_and_mental_3_to_9_preview.png
  health_and_mental_5_to_9_preview.png

METHOD

- Values 5–9 were extracted directly from the five supplied
  1000-pixel card images.
- Values 3 and 4 are newly created matching variants derived from the
  complete 5–9 reference set.
- The new hearts use the same 67×81-pixel canvas and 63×77-pixel
  occupied silhouette as the extracted hearts.
- The new brains use the same 90×74-pixel canvas and 86×70-pixel
  occupied silhouette as the extracted brains.
- Values 5–9 retain their original RGB pixels; only their transparency
  boundary was processed.
- The silhouette was expanded by one source pixel before applying a
  0.45-pixel alpha feather, preventing the smoothing from shaving off
  the smallest heart vessels or brain folds.
- All detected red and blue artwork remains at 99.8–100% full opacity;
  the remaining fraction is at 253/255 alpha and is limited to the
  smoothed outermost edge.
