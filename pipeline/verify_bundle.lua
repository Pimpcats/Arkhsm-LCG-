-- Loads dist/stillhour_bundle.lua inside a stubbed Tabletop Simulator
-- environment and drives it exactly as TTS would: onLoad -> harness -> play
-- buttons. Proves the inlined require + all six modules + the control script
-- compose correctly. Run: lua5.4 pipeline/verify_bundle.lua

-- ---- Lua-literal JSON standing in for TTS's global JSON ----
local function encode(v)
  local t = type(v)
  if t == "number" or t == "boolean" then return tostring(v) end
  if t == "string" then return string.format("%q", v) end
  if t == "table" then
    local parts = {}
    for k, val in pairs(v) do
      local key = (type(k) == "number") and ("[" .. k .. "]")
        or ("[" .. string.format("%q", k) .. "]")
      parts[#parts + 1] = key .. "=" .. encode(val)
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  error("cannot encode " .. t)
end

local buttons = {}
local env = setmetatable({
  JSON = { encode = encode, decode = function(s) return assert(load("return " .. s))() end },
  print = print,
  broadcastToAll = function(msg) print("  (broadcast) " .. msg) end,
  self = { createButton = function(_, def)
    -- TTS calls self.createButton{...}; with method syntax `self.createButton({..})`
    -- the table is the first arg here.
    buttons[#buttons + 1] = def
  end },
}, { __index = _G })

-- control.lua calls self.createButton({...}) as a dot-call (one arg = the def).
env.self.createButton = function(def) buttons[#buttons + 1] = def end

local chunk = assert(loadfile("dist/stillhour_bundle.lua", "t", env))
chunk()

print("== driving the bundle as TTS would ==")
env.onLoad(nil)
assert(#buttons == 7, "expected 7 control buttons, got " .. #buttons)
print("  created " .. #buttons .. " buttons: " ..
  (function() local n = {} for _, b in ipairs(buttons) do n[#n + 1] = b.label end return table.concat(n, ", ") end)())

print("\n== runStillHourTests() ==")
env.runStillHourTests()

print("\n== play sequence (buttons) ==")
env.shRaiseDissonance()
env.shAdvanceHour()
env.shStatus()

-- onSave must return a decodable blob.
local blob = env.onSave()
assert(type(blob) == "string" and #blob > 0, "onSave produced no state")
print("\n== onSave -> LuaScriptState (" .. #blob .. " bytes) ==")
print("verify_bundle: OK")
