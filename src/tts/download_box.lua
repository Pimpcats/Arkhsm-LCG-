-- THE STILL HOUR — SCED download-box placeholder (P8).
--
-- This is the small object a user adds to their SCED game. The mod's Global
-- provides GlobalApi.placeholderDownload(filename), which fetches
-- {filename}.json from the SCED-downloads release and spawns its contents in
-- place of this box (the standard SCED distribution pattern, SCED_BUILD_BRIEF §1).
--
-- The filename lives in this object's GMNotes: {"filename":"the_still_hour"}.
--
-- NOTE: verify GlobalApi.placeholderDownload's exact name/signature in your SCED
-- fork before shipping — the fallback below keeps this usable/testable if it is
-- absent (e.g. outside the mod).

function onLoad()
  self.createButton({
    click_function = "downloadStillHour",
    function_owner = self,
    label = "Download\nTHE STILL HOUR",
    position = { 0, 0.2, 0 },
    width = 1600, height = 600, font_size = 180,
    color = { 0.13, 0.11, 0.18 }, font_color = { 0.95, 0.9, 0.7 },
  })
end

function downloadStillHour()
  local ok, gm = pcall(function() return JSON.decode(self.getGMNotes() or "{}") end)
  local filename = (ok and gm and gm.filename) or "the_still_hour"
  if GlobalApi and GlobalApi.placeholderDownload then
    GlobalApi.placeholderDownload(filename)
  else
    broadcastToAll(
      "placeholderDownload is unavailable here — add this box inside the SCED mod. "
      .. "Release filename: " .. filename, { 1, 0.4, 0.4 })
  end
end
