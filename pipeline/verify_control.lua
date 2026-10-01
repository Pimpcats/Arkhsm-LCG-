-- Generic Control-token check for any campaign's bundle: load it in a stubbed
-- Tabletop Simulator environment (no SCED, no Global), drive onLoad, make
-- sure every button has a click function and runs without error, run the
-- campaign's in-engine tests, and round-trip save/load.
--
--   lua5.4 pipeline/verify_control.lua dist/<slug>_bundle.lua runCampaignTests
--
-- (The Still Hour's deeper check is pipeline/verify_bundle.lua.)
local bundle, entry = arg[1], arg[2] or "runCampaignTests"
assert(bundle, "usage: verify_control.lua <bundle.lua> [testsEntry]")

local function encode(v)
  local t = type(v)
  if t == "number" or t == "boolean" then return tostring(v) end
  if t == "string" then return string.format("%q", v) end
  if t == "nil" then return "nil" end
  if t == "table" then
    local parts = {}
    for k, val in pairs(v) do
      local key = (type(k) == "number") and ("[" .. k .. "]") or ("[" .. string.format("%q", k) .. "]")
      parts[#parts + 1] = key .. "=" .. encode(val)
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  error("cannot encode " .. t)
end

local failures = 0
local function expect(name, cond)
  print((cond and "  ok    " or "  FAIL  ") .. name)
  if not cond then failures = failures + 1 end
end

local buttons = {}
local selfObj = {
  createButton = function(def) buttons[#buttons + 1] = def ; return true end,
  clearButtons = function() buttons = {} ; return true end,
  getPosition = function() return { x = 0, y = 1, z = 0 } end,
  getGUID = function() return "abc123" end,
}
local env = setmetatable({
  JSON = { encode = encode, decode = function(s) return assert(load("return " .. s))() end },
  broadcastToAll = function(msg) print("  (broadcast) " .. msg) end,
  self = selfObj,
}, { __index = _G })

local chunk = assert(loadfile(bundle, "t", env))
chunk()
expect("onLoad exists", type(env.onLoad) == "function")
env.onLoad(nil)
expect("the Control creates buttons", #buttons > 0)
local snapshot = {}
for i, b in ipairs(buttons) do snapshot[i] = b end
for _, b in ipairs(snapshot) do
  local fn = env[b.click_function]
  expect("button '" .. tostring(b.label) .. "' has a click function", type(fn) == "function")
  if type(fn) == "function" then
    local ok, err = pcall(fn, selfObj, "White", false)
    expect("button '" .. tostring(b.label) .. "' runs without error" .. (ok and "" or (": " .. tostring(err))), ok)
  end
end
local tests = env[entry]
expect("tests entry " .. entry .. " exists", type(tests) == "function")
if type(tests) == "function" then
  local ok, res = pcall(tests)
  expect("in-engine tests run", ok)
  expect("in-engine tests pass", ok and type(res) == "table" and res.failed == 0 and res.passed > 0)
end
if type(env.onSave) == "function" then
  local saved = env.onSave()
  local ok = pcall(env.onLoad, saved)
  expect("save/load round-trips", ok and type(saved) == "string")
end
print(failures == 0 and "verify_control: OK" or ("verify_control: " .. failures .. " failure(s)"))
os.exit(failures == 0 and 0 or 1)
