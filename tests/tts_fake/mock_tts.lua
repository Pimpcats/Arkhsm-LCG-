-- Fake Tabletop Simulator scripting environment (tests only).
--
-- Executes one "Execute Lua Code" chunk the way TTS would in Global. The TTS
-- API itself lives in tests/sced_real/tts_emu.lua (the emulator that grew out
-- of this file and also boots SCED's whole table for tests/sced_real); this
-- file is its command-line front end for the relay tests:
--
--   * a preexisting object named "__Global__" supplies the Global script (the
--     SCED fixture in tests/tts_fake/sced/ uses it to stand in for SCED's
--     Global); every other preexisting object is created as on a loaded table
--   * the chunk runs in Global's script context, then the virtual clock runs
--     until nothing is scheduled (or a time limit)
--
-- Every message TTS would send to the external editor is written to stdout as
--   @@MSG <json>
-- (2 = print, 3 = Lua error, 4 = sendExternalMessage, 5 = return value) and
-- tests/tts_fake/fake_tts.py forwards it to the relay.
--
-- Usage: lua5.2 tests/tts_fake/mock_tts.lua <chunk.lua> [preexisting.json]

local dir = arg[0]:match("^(.*)[/\\]") or "."
local E = dofile(dir .. "/../sced_real/tts_emu.lua")
local J = E.J

local function emit(msg) io.write("@@MSG ", J.encode(msg), "\n") ; io.flush() end

E.onSay = function(kind, msg)
  if kind == "broadcast" then msg = "(broadcast) " .. msg end
  if kind == "log" or kind == "dialog" or kind == "physics" then return end
  emit({ messageID = 2, message = msg })
end
E.onError = function(rec)
  emit({ messageID = 3, error = rec.msg, guid = rec.guid or "-1", errorMessagePrefix = "Error in Script: " })
end
E.G.sendExternalMessage = function(t) emit({ messageID = 4, customMessage = t }) ; return true end

local function readFile(p)
  local f = assert(io.open(p, "rb"))
  local s = f:read("*a")
  f:close()
  return s
end

-- MOCK_WEB_FIXTURES=<file>: a JSON object {url: text}, what WebRequest.get answers for those URLs
-- (anything else is an offline error, as in the emulator)
local fixtures = os.getenv("MOCK_WEB_FIXTURES")
if fixtures and fixtures ~= "" then E.webFixtures = J.decode(readFile(fixtures)) end

local path, pre = arg[1], arg[2]
local save = { LuaScript = "", LuaScriptState = "", ObjectStates = {} }
if pre then
  for _, d in ipairs(J.decode(readFile(pre))) do
    if d.Name == "__Global__" then save.LuaScript = d.LuaScript or ""
    else save.ObjectStates[#save.ObjectStates + 1] = d end
  end
end
E.loadSave(save, "table")

local genv = E.getGlobalEnv()
if not genv then
  genv = setmetatable({ self = E.Global }, { __index = E.G })
  genv._G = genv
end
E.who("chunk_0", "chunk")
local chunk, err = load(readFile(path), "=chunk_0", "t", genv)
if not chunk then
  emit({ messageID = 3, error = tostring(err), guid = "-1", errorMessagePrefix = "Error in Script: " })
else
  E.onError = nil
  local ok, ret = xpcall(chunk, function(e) return tostring(e) end)
  E.onError = function(rec)
    emit({ messageID = 3, error = rec.msg, guid = rec.guid or "-1", errorMessagePrefix = "Error in Script: " })
  end
  if not ok then
    emit({ messageID = 3, error = tostring(ret), guid = "-1", errorMessagePrefix = "Error in Script: " })
  elseif ret ~= nil then
    emit({ messageID = 5, returnValue = ret })
  end
end

-- run the virtual clock until nothing is scheduled (a repeating Wait never
-- ends: stop after ten virtual minutes)
local limit = E.now + 600
while E.pendingWork() and E.now < limit do E.step() end
io.stderr:write(string.format("mock_tts: virtual time %.2fs, %d objects\n", E.now, #E.G.getObjects()))
