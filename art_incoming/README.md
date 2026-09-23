# art_incoming

Drop finished card illustrations here (any file names), commit, and tell Claude.
Claude identifies each image, imports it with `pipeline/import_art.py` into
`assets/illustrations/still_hour/<card-id>.jpg`, and clears this folder.
