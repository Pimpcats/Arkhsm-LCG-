-- THE STILL HOUR — download box.
--
-- The small object a player adds to a SCED table. Press Download: it fetches the
-- campaign box from GitHub and spawns it where this box stands, the way SCED's own
-- Download menu loads its campaigns (Global placeholder_download and
-- contentDownloadCallback: WebRequest.get of the file, then spawnObjectJSON of its
-- text). SCED's menu itself cannot load this campaign: it only reads its own
-- SCED-downloads release, and a script on an object has no access to Global's
-- GlobalApi module. The address is in this object's GMNotes ({"url": ...}); the build
-- writes it, and it names the build the box loads (the main branch for a release).
--
-- Nothing else happens here: the campaign box that arrives is the one in the Saved
-- Object (docs/LOADING.md), and its own Place does the rest.

local downloading = false

local function say(msg, color)
  broadcastToAll(msg, color or { 0.95, 0.85, 0.6 })
end

local function settings()
  local ok, gm = pcall(JSON.decode, self.getGMNotes() or "")
  if ok and type(gm) == "table" then return gm end
  return {}
end

function onLoad()
  self.createButton({
    click_function = "downloadStillHour",
    function_owner = self,
    label = "Download\nTHE STILL HOUR",
    tooltip = "Fetch the campaign from GitHub (about 1 MB) and put its box here",
    position = { 0, 0.2, 0 },
    width = 1600, height = 600, font_size = 180,
    color = { 0.13, 0.11, 0.18 }, font_color = { 0.95, 0.9, 0.7 },
  })
end

function downloadStillHour()
  if downloading then return end
  local gm = settings()
  local url = gm.url
  if type(url) ~= "string" or url == "" then
    say("This download box has no address in its notes; use the Saved Object instead (docs/LOADING.md).",
      { 1, 0.4, 0.4 })
    return
  end
  downloading = true
  say("Downloading THE STILL HOUR ...")
  log("StillHour download box: GET " .. url)
  WebRequest.get(url, function(request)
    downloading = false
    if request.is_error or request.response_code ~= 200 then
      log("StillHour download box: failed, code " .. tostring(request.response_code) .. " " .. tostring(request.error))
      say("The download failed (" .. tostring(request.error or request.response_code) ..
        "). Check the internet connection and that github.com is reachable, then press Download again.",
        { 1, 0.4, 0.4 })
      return
    end
    local pos, rot = self.getPosition(), self.getRotation()
    local ok, err = pcall(spawnObjectJSON, {
      json = request.text,
      position = { pos.x, pos.y + 1, pos.z },
      rotation = { rot.x, rot.y, rot.z },
      callback_function = function(obj)
        log("StillHour download box: spawned " .. tostring(obj.getName()))
        say("THE STILL HOUR is on the table. Press Place on its box (docs/LOADING.md, step 3).")
        if not self.isDestroyed() then self.destruct() end
      end,
    })
    if not ok then
      log("StillHour download box: could not spawn: " .. tostring(err))
      say("The campaign downloaded but could not be put on the table (see the log).", { 1, 0.4, 0.4 })
    end
  end)
end
