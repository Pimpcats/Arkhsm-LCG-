-- Headless Tabletop Simulator emulator (tests only).
--
-- Grown from tests/tts_fake/mock_tts.lua (same object model and conventions),
-- extended far enough to boot a whole saved game: SCED's Global and every
-- scripted object on its table, and this repository's campaign objects. It is
-- a stand-in for TTS, not a physics engine. What it models:
--
--   * objects with GUIDs (a colliding GUID is replaced, like TTS), per-object
--     script environments with `self`, `_G` = that script's globals and a
--     `require` resolving modules against the given source folders (what the
--     TTS bundler's prelude does), onLoad(script_state)/onSave, buttons,
--     inputs, context menus, States, getData/getJSON, tags, memo, UI (tracked,
--     never rendered), decals, snap points, vector lines, Book (PDF)
--   * containers: bags and decks (takeObject by index/guid, putObject, card +
--     card -> deck, the last card of a deck becoming a lone card, shuffle,
--     deal, reset), tryObjectEnterContainer / tryObjectEnter vetoes
--   * a simulated clock: Wait.frames/time/condition/stop driven one 1/60 s
--     frame at a time by the harness (E.step / E.run), deferred destruction
--     (an object is removed at the end of the frame it was destructed in),
--     object scripts loading one frame after a spawn, spawn callbacks
--   * approximate physics: bounds from each object's type and scale (with
--     overrides for SCED's big boards), Physics.cast (box/sphere/ray against
--     axis-aligned bounds), a "landing" a few frames after a spawn or move
--     (the object settles on the highest thing under its centre, drops into a
--     bag it lands on, and onCollisionEnter/Exit fire), scripting/hand zones
--     (onObjectEnterZone/LeaveZone, getZones)
--   * universal events: onObjectSpawn/Destroy/EnterContainer/LeaveContainer/
--     EnterZone/LeaveZone/Drop/PickUp/Rotate/StateChange, onUpdate per frame
--   * Global (getVar/setVar/call/getTable/UI/...), Player/Hands/Turns/Notes/
--     Time/Info/Grid/Lighting stubs, JSON, Vector, Color, logging capture,
--     WebRequest (local fixtures only, otherwise an offline error; never the
--     network), startLuaCoroutine
--
-- Every script error is captured with a traceback and the script it came
-- from; accesses to unknown object members are recorded as emulator gaps.
-- Works under Lua 5.2 (closest to TTS's MoonSharp) and 5.4.

local E = {}

local here = (debug.getinfo(1, "S").source:match("^@(.*)[/\\]") or ".")
local J = dofile(here .. "/../tts_fake/json.lua")
E.J = J

local unpack = table.unpack or unpack
local FRAME = 1 / 60

------------------------------------------------------------------ utils --

local function deepcopy(v, seen)
  if type(v) ~= "table" then return v end
  seen = seen or {}
  if seen[v] then return seen[v] end
  local t = {}
  seen[v] = t
  for k, x in pairs(v) do t[deepcopy(k, seen)] = deepcopy(x, seen) end
  return setmetatable(t, getmetatable(v))
end
E.deepcopy = deepcopy

-- plain copy for object data: drops metatables (data is plain JSON-ish)
local function datacopy(v)
  if type(v) ~= "table" then return v end
  local t = {}
  for k, x in pairs(v) do
    if type(x) ~= "function" then t[k] = datacopy(x) end
  end
  return t
end
E.datacopy = datacopy

-- deterministic PRNG (xorshift) for GUIDs and shuffles: runs are repeatable
local rngState = 0x2545F491
local function rand()
  rngState = (rngState * 1103515245 + 12345) % 2147483648
  return rngState / 2147483648
end
E.rand = rand
function E.seed(n) rngState = n % 2147483648 end

------------------------------------------------------------------ JSON --

local function jsonDecode(s)
  if type(s) ~= "string" then return nil end
  if s:find("^%s*$") then return nil end
  local ok, v = pcall(J.decode, s)
  if ok then return v end
  E.warn("JSON.decode failed: " .. tostring(v))
  return nil
end

local function isArray(t)
  local n = 0
  for k in pairs(t) do
    if type(k) ~= "number" then return false end
    n = n + 1
  end
  for i = 1, n do if t[i] == nil then return false end end
  return n > 0
end

local function prettyEncode(v, indent)
  indent = indent or ""
  if type(v) ~= "table" or next(v) == nil then return J.encode(v) end
  local inner = indent .. "  "
  local parts = {}
  if isArray(v) then
    for i = 1, #v do parts[i] = inner .. prettyEncode(v[i], inner) end
    return "[\n" .. table.concat(parts, ",\n") .. "\n" .. indent .. "]"
  end
  local keys = {}
  for k in pairs(v) do if type(v[k]) ~= "function" then keys[#keys + 1] = tostring(k) end end
  table.sort(keys)
  for i, k in ipairs(keys) do
    local val = v[k]
    if val == nil then val = v[tonumber(k)] end
    parts[i] = inner .. J.encode(k) .. ": " .. prettyEncode(val, inner)
  end
  return "{\n" .. table.concat(parts, ",\n") .. "\n" .. indent .. "}"
end

E.JSON = {
  decode = jsonDecode,
  encode = function(v) return J.encode(v) end,
  encode_pretty = function(v) return prettyEncode(v) end,
}

------------------------------------------------------------- Vector/Color --

local Vector = {}
E.Vector = Vector
local VKEY = { "x", "y", "z" }
Vector.__index = function(t, k)
  if type(k) == "number" then return rawget(t, VKEY[k]) end
  return Vector[k]
end
Vector.__newindex = function(t, k, v)
  if type(k) == "number" and VKEY[k] then rawset(t, VKEY[k], v) else rawset(t, k, v) end
end
local function vnew(x, y, z)
  if type(x) == "table" then
    x, y, z = (x.x or x[1] or 0), (x.y or x[2] or 0), (x.z or x[3] or 0)
  end
  return setmetatable({ x = x or 0, y = y or 0, z = z or 0 }, Vector)
end
Vector.new = function(...) return vnew(...) end
setmetatable(Vector, { __call = function(_, ...) return vnew(...) end })
local function isnum(v) return type(v) == "number" end
Vector.__add = function(a, b) return vnew(a.x + b.x, a.y + b.y, a.z + b.z) end
Vector.__sub = function(a, b) return vnew(a.x - b.x, a.y - b.y, a.z - b.z) end
Vector.__unm = function(a) return vnew(-a.x, -a.y, -a.z) end
Vector.__mul = function(a, b)
  if isnum(a) then a, b = b, a end
  if isnum(b) then return vnew(a.x * b, a.y * b, a.z * b) end
  return vnew(a.x * b.x, a.y * b.y, a.z * b.z)
end
Vector.__eq = function(a, b) return a:equals(b) end
Vector.__tostring = function(a) return a:string() end
function Vector:setAt(k, v) self[k] = v ; return self end
function Vector:set(x, y, z)
  if type(x) == "table" then x, y, z = x.x or x[1], x.y or x[2], x.z or x[3] end
  self.x, self.y, self.z = x or self.x, y or self.y, z or self.z
  return self
end
function Vector:get() return self.x, self.y, self.z end
function Vector:copy() return vnew(self.x, self.y, self.z) end
function Vector:add(v) self.x, self.y, self.z = self.x + v.x, self.y + v.y, self.z + v.z ; return self end
function Vector:sub(v) self.x, self.y, self.z = self.x - v.x, self.y - v.y, self.z - v.z ; return self end
function Vector:scale(v)
  if isnum(v) then self.x, self.y, self.z = self.x * v, self.y * v, self.z * v
  else self.x, self.y, self.z = self.x * (v.x or v[1]), self.y * (v.y or v[2]), self.z * (v.z or v[3]) end
  return self
end
function Vector:clamp(m)
  local mag = self:magnitude()
  if mag > m and mag > 0 then self:scale(m / mag) end
  return self
end
function Vector:dot(v) return self.x * v.x + self.y * v.y + self.z * v.z end
function Vector:cross(v)
  return vnew(self.y * v.z - self.z * v.y, self.z * v.x - self.x * v.z, self.x * v.y - self.y * v.x)
end
function Vector:sqrMagnitude() return self.x ^ 2 + self.y ^ 2 + self.z ^ 2 end
function Vector:magnitude() return math.sqrt(self:sqrMagnitude()) end
function Vector:sqrDistance(v) return (self.x - v.x) ^ 2 + (self.y - v.y) ^ 2 + (self.z - v.z) ^ 2 end
function Vector:distance(v) return math.sqrt(self:sqrDistance(v)) end
function Vector:normalize()
  local m = self:magnitude()
  if m > 0 then self:scale(1 / m) end
  return self
end
function Vector:normalized() return self:copy():normalize() end
function Vector:inverse() return vnew(-self.x, -self.y, -self.z) end
function Vector:moveTowards(target, maxDelta)
  local d = vnew(target) - self
  local m = d:magnitude()
  if m <= maxDelta or m == 0 then return self:set(target.x, target.y, target.z) end
  return self:add(d:scale(maxDelta / m))
end
function Vector:rotateOver(axis, angle)
  local a, b
  if axis == "x" then a, b = "y", "z" elseif axis == "y" then a, b = "z", "x" else a, b = "x", "y" end
  local r = math.rad(angle)
  local c, s = math.cos(r), math.sin(r)
  self[a], self[b] = self[a] * c - self[b] * s, self[a] * s + self[b] * c
  return self
end
function Vector:angle(v)
  local d = self:magnitude() * v:magnitude()
  if d == 0 then return 0 end
  return math.deg(math.acos(math.max(-1, math.min(1, self:dot(v) / d))))
end
function Vector:heading(axis)
  if axis == "x" then return math.deg(math.atan2 and math.atan2(self.y, self.z) or math.atan(self.y, self.z)) end
  if axis == "z" then return math.deg(math.atan2 and math.atan2(self.x, self.y) or math.atan(self.x, self.y)) end
  local h = math.deg(math.atan2 and math.atan2(self.x, self.z) or math.atan(self.x, self.z))
  return h
end
function Vector:equals(v, margin)
  margin = margin or 1e-3
  return math.abs(self.x - v.x) <= margin and math.abs(self.y - v.y) <= margin and math.abs(self.z - v.z) <= margin
end
function Vector:string(prefix)
  return string.format("%s{ %s, %s, %s }", prefix and (prefix .. ": ") or "", self.x, self.y, self.z)
end
function Vector:lerp(target, t)
  return self:set(self.x + (target.x - self.x) * t, self.y + (target.y - self.y) * t, self.z + (target.z - self.z) * t)
end
function Vector:project(v)
  local m = v:sqrMagnitude()
  if m == 0 then return self:set(0, 0, 0) end
  local k = self:dot(v) / m
  return self:set(v.x * k, v.y * k, v.z * k)
end
function Vector:projectOnPlane(n) return self:sub(self:copy():project(n)) end
function Vector:reflect(n)
  local k = 2 * self:dot(n) / math.max(1e-9, n:sqrMagnitude())
  return self:sub(vnew(n):scale(k))
end
function Vector.between(a, b) return vnew(b) - vnew(a) end
function Vector.min(a, b) return vnew(math.min(a.x, b.x), math.min(a.y, b.y), math.min(a.z, b.z)) end
function Vector.max(a, b) return vnew(math.max(a.x, b.x), math.max(a.y, b.y), math.max(a.z, b.z)) end

local Color = {}
E.Color = Color
local CKEY = { "r", "g", "b", "a" }
local NAMED = {
  White = { 1, 1, 1 }, Brown = { 0.443, 0.231, 0.09 }, Red = { 0.856, 0.1, 0.094 },
  Orange = { 0.956, 0.392, 0.113 }, Yellow = { 0.905, 0.898, 0.172 }, Green = { 0.192, 0.701, 0.168 },
  Teal = { 0.129, 0.694, 0.607 }, Blue = { 0.118, 0.53, 1 }, Purple = { 0.627, 0.125, 0.941 },
  Pink = { 0.96, 0.439, 0.807 }, Grey = { 0.5, 0.5, 0.5 }, Black = { 0.25, 0.25, 0.25 },
}
Color.__index = function(t, k)
  if type(k) == "number" then return rawget(t, CKEY[k]) end
  return Color[k]
end
Color.__newindex = function(t, k, v)
  if type(k) == "number" and CKEY[k] then rawset(t, CKEY[k], v) else rawset(t, k, v) end
end
local function cnew(r, g, b, a)
  if type(r) == "table" then
    r, g, b, a = (r.r or r[1] or 0), (r.g or r[2] or 0), (r.b or r[3] or 0), (r.a or r[4] or 1)
  end
  return setmetatable({ r = r or 0, g = g or 0, b = b or 0, a = a or 1 }, Color)
end
local function fromString(s)
  if type(s) ~= "string" then return nil end
  for name, c in pairs(NAMED) do
    if name:lower() == s:lower() then return cnew(c[1], c[2], c[3], 1) end
  end
  local hex = s:gsub("^#", "")
  if hex:find("^%x%x%x%x%x%x") then
    local a = #hex >= 8 and tonumber(hex:sub(7, 8), 16) / 255 or 1
    return cnew(tonumber(hex:sub(1, 2), 16) / 255, tonumber(hex:sub(3, 4), 16) / 255,
      tonumber(hex:sub(5, 6), 16) / 255, a)
  end
  return nil
end
setmetatable(Color, {
  __call = function(_, ...) return cnew(...) end,
  __index = function(_, k)
    local c = NAMED[k]
    if c then return cnew(c[1], c[2], c[3], 1) end
    return nil
  end,
})
Color.new = function(...) return cnew(...) end
Color.fromString = fromString
Color.fromHex = fromString
Color.list = { "White", "Brown", "Red", "Orange", "Yellow", "Green", "Teal", "Blue", "Purple", "Pink", "Grey", "Black" }
Color.__eq = function(a, b) return a:equals(b) end
Color.__tostring = function(c) return c:toString() end
function Color:get() return self.r, self.g, self.b, self.a end
function Color:copy() return cnew(self.r, self.g, self.b, self.a) end
function Color:setAt(k, v) self[k] = v ; return self end
function Color:set(r, g, b, a) self.r, self.g, self.b, self.a = r or self.r, g or self.g, b or self.b, a or self.a ; return self end
function Color:equals(o, m)
  m = m or 0.01
  return math.abs(self.r - o.r) <= m and math.abs(self.g - o.g) <= m and math.abs(self.b - o.b) <= m
    and math.abs((self.a or 1) - (o.a or 1)) <= m
end
function Color:toHex(alpha)
  local s = string.format("%02x%02x%02x", math.floor(self.r * 255 + 0.5), math.floor(self.g * 255 + 0.5),
    math.floor(self.b * 255 + 0.5))
  if alpha then s = s .. string.format("%02x", math.floor((self.a or 1) * 255 + 0.5)) end
  return s
end
function Color:toString(tol)
  for name, c in pairs(NAMED) do
    if self:equals(cnew(c[1], c[2], c[3], self.a), tol or 0.01) then return name end
  end
  return nil
end
function Color:lerp(o, t)
  return self:set(self.r + (o.r - self.r) * t, self.g + (o.g - self.g) * t, self.b + (o.b - self.b) * t,
    (self.a or 1) + ((o.a or 1) - (self.a or 1)) * t)
end

------------------------------------------------------------- reporting --

E.errors = {}        -- { where=, msg=, trace=, t=, origin= }
E.warnings = {}
E.gaps = {}          -- "Type.member" -> count
E.log = {}           -- printed / broadcast lines
E.phase = "boot"
E.quiet = true

function E.warn(msg)
  E.warnings[#E.warnings + 1] = string.format("[%.2fs] %s", E.now or 0, msg)
end

local function traceback(err)
  return debug.traceback(tostring(err), 2)
end

--- Run fn(...) protected; a Lua error is recorded against `who`.
function E.protect(who, fn, ...)
  local args = { n = select("#", ...), ... }
  local ok, res = xpcall(function() return fn(unpack(args, 1, args.n)) end, traceback)
  if not ok then
    local origin = type(who) == "table" and who.origin or "?"
    local label = type(who) == "table" and who.label or tostring(who)
    E.errors[#E.errors + 1] = { where = label, origin = origin, phase = E.phase,
      msg = (tostring(res):match("^[^\n]*")), trace = res, t = E.now }
    if not E.quiet then io.stderr:write("[lua error] " .. label .. ": " .. tostring(res) .. "\n") end
    if E.onError then E.onError(E.errors[#E.errors]) end
    return false, res
  end
  return true, res
end

local function say(kind, msg)
  E.log[#E.log + 1] = { kind = kind, msg = msg, t = E.now }
  if E.echo then print(string.format("  [%s] %s", kind, msg)) end
  if E.onSay then E.onSay(kind, msg) end
end
E.say = say

------------------------------------------------------------------- clock --

E.now, E.frame = 0, 0
local timers, timerSeq = {}, 0
local cancelled = {}

local function addTimer(t)
  timerSeq = timerSeq + 1
  t.id = timerSeq
  timers[#timers + 1] = t
  return timerSeq
end

local currentWho = { label = "harness", origin = "harness" }
local function who() return currentWho end

local Wait = {}
E.Wait = Wait
function Wait.frames(fn, n)
  local owner = who()
  return addTimer({ frame = E.frame + math.max(1, math.floor(n or 1)), fn = fn, owner = owner })
end
function Wait.time(fn, secs, reps)
  local owner = who()
  secs = tonumber(secs) or 0
  local t = { at = E.now + secs, fn = fn, owner = owner, every = secs, reps = reps or 1 }
  return addTimer(t)
end
function Wait.condition(fn, cond, timeout, timeoutFn)
  local owner = who()
  return addTimer({ cond = cond, fn = fn, owner = owner, frame = E.frame + 1,
    deadline = timeout and (E.now + timeout) or nil, timeoutFn = timeoutFn })
end
function Wait.stop(id) if id then cancelled[id] = true end end
function Wait.stopAll() for _, t in ipairs(timers) do cancelled[t.id] = true end end

------------------------------------------------------------------ world --

E.objects = {}            -- top-level objects in creation order
local byGuid = {}
local S = setmetatable({}, { __mode = "k" })   -- object -> state
E.S = S
local pendingDestroy = {}
local pendingLoad = {}    -- objects whose scripts run next frame
local globalEnv, GlobalObj
E.srcDirs = {}            -- require() search folders
E.envs = {}               -- list of { env=, obj= } with scripts (for events)

local function isAlive(o) local st = S[o] return st and not st.removed end

local function newGuid(want)
  if type(want) == "string" and #want > 0 and not byGuid[want] then return want end
  local g
  repeat
    g = string.format("%06x", math.floor(rand() * 0xffffff))
  until not byGuid[g]
  return g
end

local TYPE = {
  Bag = "Bag", Custom_Model_Bag = "Bag", Infinite_Bag = "Infinite", Custom_Model_Infinite_Bag = "Infinite",
  Deck = "Deck", DeckCustom = "Deck", Card = "Card", CardCustom = "Card",
  Custom_Tile = "Tile", Custom_Tile_Stack = "Stack", Custom_Token = "Tile", Custom_Token_Stack = "Stack",
  ScriptingTrigger = "Scripting", HandTrigger = "Hand", FogOfWarTrigger = "Fog", RandomizeTrigger = "Scripting",
  LayoutZone = "Layout",
  BlockSquare = "Block", BlockRectangle = "Block", BlockTriangle = "Block",
  ["3DText"] = "3D Text", Notecard = "Notecard", Counter = "Counter", Custom_Dice = "Dice",
  Custom_Board = "Board", Figurine_Custom = "Figurine", Tablet = "Tablet", Custom_PDF = "Generic",
  Chip_10 = "Chip", Chip_50 = "Chip", Chip_100 = "Chip", Chip_500 = "Chip", Chip_1000 = "Chip",
}
local function typeOf(name) return TYPE[name] or "Generic" end
E.typeOf = typeOf

-- local (unscaled) sizes; x, y, z
local SIZE = {
  Card = { 2.2, 0.02, 3.05 }, Deck = { 2.2, 0.02, 3.05 },
  Tile = { 2, 0.2, 2 }, Stack = { 2, 0.2, 2 },
  Bag = { 1.5, 1.5, 1.5 }, Infinite = { 1.5, 1.5, 1.5 },
  Block = { 1, 1, 1 }, Scripting = { 1, 1, 1 }, Hand = { 1, 1, 1 }, Fog = { 1, 1, 1 }, Layout = { 1, 1, 1 },
  ["3D Text"] = { 1, 0.05, 0.3 }, Notecard = { 2, 0.05, 1.3 }, Counter = { 1.2, 0.3, 0.6 },
  Generic = { 1, 0.4, 1 }, Chip = { 0.8, 0.1, 0.8 }, Dice = { 1, 1, 1 }, Board = { 10, 0.2, 10 },
  Figurine = { 1, 2, 1 }, Tablet = { 2, 0.2, 1.5 },
}
-- per-GUID local sizes for boards whose image aspect TTS knows and we do not
-- (derived from SCED's own coordinates: MythosArea's area data, the play
-- area's snap grid, the playmats' card slots)
E.sizeOverride = {}
E.nameSizeOverride = {
  Custom_Model_Bag = { 0.7, 0.7, 0.7 },
  Custom_PDF = { 2, 0.1, 2.6 },
  Custom_Model = { 0.8, 0.4, 0.8 },
  Custom_Assetbundle = { 1, 1, 1 },
}

------------------------------------------------------------ transforms --

local function rotY(v, deg)
  local r = math.rad(deg)
  local c, s = math.cos(r), math.sin(r)
  return v.x * c + v.z * s, v.y, -v.x * s + v.z * c
end
local function rotX(x, y, z, deg)
  local r = math.rad(deg)
  local c, s = math.cos(r), math.sin(r)
  return x, y * c - z * s, y * s + z * c
end
local function rotZ(x, y, z, deg)
  local r = math.rad(deg)
  local c, s = math.cos(r), math.sin(r)
  return x * c - y * s, x * s + y * c, z
end
-- Unity applies Z, then X, then Y
local function rotate(v, rot)
  local x, y, z = rotZ(v.x, v.y, v.z, rot.z)
  x, y, z = rotX(x, y, z, rot.x)
  x, y, z = rotY({ x = x, y = y, z = z }, rot.y)
  return x, y, z
end
local function unrotate(v, rot)
  local x, y, z = rotY(v, -rot.y)
  x, y, z = rotX(x, y, z, -rot.x)
  x, y, z = rotZ(x, y, z, -rot.z)
  return x, y, z
end
E.rotate = rotate

local function vecOf(p)
  if p == nil then return nil end
  return { x = p.x or p[1] or 0, y = p.y or p[2] or 0, z = p.z or p[3] or 0 }
end

----------------------------------------------------------------- events --

local function envList()
  local l = {}
  if globalEnv then l[#l + 1] = { env = globalEnv, who = globalEnv.__who } end
  for _, o in ipairs(E.objects) do
    local st = S[o]
    if st and st.env and not st.removed then l[#l + 1] = { env = st.env, who = st.env.__who } end
  end
  return l
end

local function callIn(entry, name, ...)
  local fn = rawget(entry.env, name)
  if type(fn) ~= "function" then return true, nil end
  local prev = currentWho
  currentWho = entry.who
  local ok, res = E.protect(entry.who, fn, ...)
  currentWho = prev
  return ok, res
end

--- Fire a universal event in Global and every object script.
function E.fire(name, ...)
  for _, e in ipairs(envList()) do callIn(e, name, ...) end
end

--- tryObjectEnterContainer vetoes: Global/any script, and the container's
-- own tryObjectEnter / filterObjectEnter.
local function mayEnter(container, obj)
  for _, e in ipairs(envList()) do
    local ok, res = callIn(e, "tryObjectEnterContainer", container, obj)
    if ok and res == false then return false end
  end
  local st = S[container]
  if st and st.env then
    for _, fname in ipairs({ "tryObjectEnter", "filterObjectEnter" }) do
      local ok, res = callIn({ env = st.env, who = st.env.__who }, fname, obj)
      if ok and res == false then return false end
    end
  end
  return true
end

------------------------------------------------------------------ bounds --

local function localSize(o)
  local st = S[o]
  local d = st.data
  local s = E.sizeOverride[st.guid] or E.nameSizeOverride[d.Name] or SIZE[typeOf(d.Name)] or SIZE.Generic
  local x, y, z = s[1], s[2], s[3]
  if d.Name == "Custom_Tile" or d.Name == "Custom_Token" then
    local ct = (d.CustomImage or {}).CustomTile or {}
    if ct.Thickness then y = ct.Thickness end
  end
  if typeOf(d.Name) == "Deck" then y = math.max(0.02, 0.02 * #(st.contained or {})) end
  return x, y, z
end

-- axis-aligned world bounds {min={x,y,z}, max={x,y,z}, center, size}
local function aabb(o)
  local st = S[o]
  local lx, ly, lz = localSize(o)
  lx, ly, lz = lx * st.scale.x, ly * st.scale.y, lz * st.scale.z
  local minx, miny, minz, maxx, maxy, maxz = math.huge, math.huge, math.huge, -math.huge, -math.huge, -math.huge
  for _, sx in ipairs({ -0.5, 0.5 }) do
    for _, sy in ipairs({ -0.5, 0.5 }) do
      for _, sz in ipairs({ -0.5, 0.5 }) do
        local x, y, z = rotate({ x = lx * sx, y = ly * sy, z = lz * sz }, st.rot)
        minx, maxx = math.min(minx, x), math.max(maxx, x)
        miny, maxy = math.min(miny, y), math.max(maxy, y)
        minz, maxz = math.min(minz, z), math.max(maxz, z)
      end
    end
  end
  local p = st.pos
  return { min = { x = p.x + minx, y = p.y + miny, z = p.z + minz },
           max = { x = p.x + maxx, y = p.y + maxy, z = p.z + maxz },
           center = { x = p.x, y = p.y, z = p.z },
           size = { x = maxx - minx, y = maxy - miny, z = maxz - minz } }
end
E.aabb = aabb

local function isZone(o)
  local t = typeOf(S[o].data.Name)
  return t == "Scripting" or t == "Hand" or t == "Fog" or t == "Layout"
end
E.isZone = isZone

local function overlapXZ(a, b, pad)
  pad = pad or 0
  return a.min.x < b.max.x + pad and a.max.x > b.min.x - pad and a.min.z < b.max.z + pad and a.max.z > b.min.z - pad
end
local function containsXZ(b, p)
  return p.x >= b.min.x and p.x <= b.max.x and p.z >= b.min.z and p.z <= b.max.z
end
local function containsXYZ(b, p)
  return containsXZ(b, p) and p.y >= b.min.y and p.y <= b.max.y
end

------------------------------------------------------------------- zones --

local function zonesAt(o)
  local list = {}
  local p = S[o].pos
  for _, z in ipairs(E.objects) do
    if z ~= o and isZone(z) and not S[z].removed and containsXYZ(aabb(z), p) then list[#list + 1] = z end
  end
  return list
end

local function updateZones(o)
  local st = S[o]
  if st.removed or isZone(o) then return end
  local now = {}
  for _, z in ipairs(zonesAt(o)) do now[z] = true end
  local before = st.zones or {}
  st.zones = now
  for z in pairs(before) do if not now[z] and isAlive(z) then E.fire("onObjectLeaveZone", z, o) end end
  for z in pairs(now) do if not before[z] then E.fire("onObjectEnterZone", z, o) end end
end
E.updateZones = updateZones

--------------------------------------------------------------- landing --

local makeObject, spawnData, loadScript, removeNow

local function scheduleLanding(o, frames)
  local st = S[o]
  if st.locked or st.removed then return end
  st.resting = false
  st.landFrame = E.frame + (frames or 8)
end

local function collide(receiver, mover, name)
  local rs = S[receiver]
  if rs and rs.env and not rs.removed then
    callIn({ env = rs.env, who = rs.env.__who }, name, {
      collision_object = mover, contact_points = { Vector(S[mover].pos) }, relative_velocity = Vector(0, -1, 0) })
  end
end

local function land(o)
  local st = S[o]
  st.landFrame = nil
  if st.removed or st.inContainer then return end
  local came = st.cameFrom      -- the container it was just taken from
  st.cameFrom = nil
  local b = aabb(o)
  local half = b.size.y / 2
  local mtype0 = typeOf(st.data.Name)
  if mtype0 ~= "Bag" and mtype0 ~= "Infinite" then
    -- spawned or dropped inside a bag's volume: the bag takes it (SCED adds
    -- chaos tokens by spawning them just inside the bag)
    for _, other in ipairs(E.objects) do
      local os_ = S[other]
      local ot = os_ and typeOf(os_.data.Name)
      if other ~= o and other ~= came and not os_.removed and (ot == "Bag" or ot == "Infinite") and containsXYZ(aabb(other), st.pos) then
        if mayEnter(other, o) then
          E.physicsEntries = (E.physicsEntries or 0) + 1
          E.fellInto = E.fellInto or {}
          E.fellInto[#E.fellInto + 1] = { obj = st.data.Nickname or st.data.Name, guid = st.guid,
            bag = os_.data.Nickname or os_.data.Name, bagGuid = os_.guid, t = E.now, origin = st.origin }
          E.say("physics", string.format("%s (%s) landed inside %s (%s)", st.data.Nickname or st.data.Name,
            st.guid, os_.data.Nickname or os_.data.Name, os_.guid))
          E.putInto(other, o)
          return
        end
      end
    end
  end
  local support, top = nil, -math.huge
  local touching = {}
  for _, other in ipairs(E.objects) do
    local os_ = S[other]
    if other ~= o and not os_.removed and not isZone(other) then
      local ob = aabb(other)
      if overlapXZ(b, ob) and ob.max.y <= st.pos.y + 0.05 then
        touching[#touching + 1] = { obj = other, top = ob.max.y, box = ob }
        if containsXZ(ob, st.pos) and ob.max.y > top then support, top = other, ob.max.y end
      end
    end
  end
  if support then
    -- a bag it lands on takes it in (how SCED puts spawned tokens in a bag)
    local stype = typeOf(S[support].data.Name)
    local mtype = typeOf(st.data.Name)
    if support ~= came and (stype == "Bag" or stype == "Infinite") and mtype ~= "Bag" and mtype ~= "Infinite" then
      if mayEnter(support, o) then
        E.physicsEntries = (E.physicsEntries or 0) + 1
        E.fellInto = E.fellInto or {}
        E.fellInto[#E.fellInto + 1] = { obj = st.data.Nickname or st.data.Name, guid = st.guid,
          bag = S[support].data.Nickname or S[support].data.Name, bagGuid = S[support].guid, t = E.now,
          origin = st.origin }
        E.say("physics", string.format("%s (%s) fell into %s (%s)", st.data.Nickname or st.data.Name, st.guid,
          S[support].data.Nickname or S[support].data.Name, S[support].guid))
        E.putInto(support, o)
        return
      end
    end
    st.pos = { x = st.pos.x, y = top + half, z = st.pos.z }
  end
  st.resting = true
  -- contacts: everything under it at the support's height
  local now = {}
  for _, t in ipairs(touching) do
    if t.top >= top - 0.3 then now[t.obj] = true end
  end
  local before = st.contacts or {}
  st.contacts = now
  for other in pairs(before) do
    if not now[other] and isAlive(other) then
      collide(other, o, "onCollisionExit")
      collide(o, other, "onCollisionExit")
    end
  end
  for other in pairs(now) do
    if not before[other] then
      collide(other, o, "onCollisionEnter")
      collide(o, other, "onCollisionEnter")
    end
  end
  updateZones(o)
end
E.land = land

---------------------------------------------------------------- Physics --

local Physics = {}
E.Physics = Physics
-- box / sphere / ray cast against axis-aligned bounds; zones are triggers
-- and are never hit
function Physics.cast(p)
  p = p or {}
  local origin = vecOf(p.origin) or { x = 0, y = 0, z = 0 }
  local dir = vecOf(p.direction) or { x = 0, y = -1, z = 0 }
  local dist = tonumber(p.max_distance) or 0
  if (p.type or 1) == 1 and dist == 0 then dist = 1000 end
  local size = vecOf(p.size) or { x = 0.01, y = 0.01, z = 0.01 }
  local ty = p.type or 1
  local hx, hy, hz
  if ty == 3 then
    local ori = vecOf(p.orientation) or { x = 0, y = 0, z = 0 }
    hx, hy, hz = 0, 0, 0
    for _, sx in ipairs({ -0.5, 0.5 }) do
      for _, sy in ipairs({ -0.5, 0.5 }) do
        for _, sz in ipairs({ -0.5, 0.5 }) do
          local x, y, z = rotate({ x = size.x * sx, y = size.y * sy, z = size.z * sz }, ori)
          hx, hy, hz = math.max(hx, math.abs(x)), math.max(hy, math.abs(y)), math.max(hz, math.abs(z))
        end
      end
    end
  elseif ty == 2 then
    local r = (size.x or 1) / 2
    hx, hy, hz = r, r, r
  else
    hx, hy, hz = 0.001, 0.001, 0.001
  end
  local ex = { x = origin.x + dir.x * dist, y = origin.y + dir.y * dist, z = origin.z + dir.z * dist }
  local box = { min = { x = math.min(origin.x, ex.x) - hx, y = math.min(origin.y, ex.y) - hy, z = math.min(origin.z, ex.z) - hz },
                max = { x = math.max(origin.x, ex.x) + hx, y = math.max(origin.y, ex.y) + hy, z = math.max(origin.z, ex.z) + hz } }
  local hits = {}
  for _, o in ipairs(E.objects) do
    local st = S[o]
    if not st.removed and not isZone(o) then
      local b = aabb(o)
      if b.min.x <= box.max.x and b.max.x >= box.min.x and b.min.y <= box.max.y and b.max.y >= box.min.y
        and b.min.z <= box.max.z and b.max.z >= box.min.z then
        local d = (st.pos.x - origin.x) * dir.x + (st.pos.y - origin.y) * dir.y + (st.pos.z - origin.z) * dir.z
        hits[#hits + 1] = { hit_object = o, point = Vector(st.pos), normal = Vector(0, 1, 0), distance = math.max(0, d) }
      end
    end
  end
  table.sort(hits, function(a, b) return a.distance < b.distance end)
  return hits
end
function Physics.getGravity() return Vector(0, -9.81, 0) end
function Physics.setGravity() return true end
Physics.play_area = 0.5

------------------------------------------------------------ UI (tracked) --

local function makeUI(ownerLabel)
  local ui = { xml = "", xmlTable = {}, attrs = {}, assets = {}, calls = 0 }
  local api = {}
  local function track() ui.calls = ui.calls + 1 end
  function api.setXml(x) track() ui.xml = x or "" return true end
  function api.getXml() return ui.xml end
  function api.setXmlTable(t) track() ui.xmlTable = t or {} return true end
  function api.getXmlTable() return deepcopy(ui.xmlTable) end
  function api.setAttribute(id, k, v) track() ui.attrs[id] = ui.attrs[id] or {} ; ui.attrs[id][k] = v return true end
  function api.setAttributes(id, t) track() ui.attrs[id] = ui.attrs[id] or {} for k, v in pairs(t or {}) do ui.attrs[id][k] = v end return true end
  function api.getAttribute(id, k) return (ui.attrs[id] or {})[k] end
  function api.getAttributes(id) return deepcopy(ui.attrs[id] or {}) end
  function api.show(id) return api.setAttribute(id, "active", true) end
  function api.hide(id) return api.setAttribute(id, "active", false) end
  function api.setValue(id, v) return api.setAttribute(id, "text", v) end
  function api.getValue(id) return (ui.attrs[id] or {}).text end
  function api.setCustomAssets(a) ui.assets = a or {} return true end
  function api.getCustomAssets() return deepcopy(ui.assets) end
  function api.setClass(id, v) return api.setAttribute(id, "class", v) end
  api.loading = false
  api.__state = ui
  return api
end

------------------------------------------------------------------ objects --

local SETTABLE = {
  interactable = true, tooltip = true, resting = true, use_gravity = true, use_grid = true, use_snap_points = true,
  use_hands = true, auto_raise = true, sticky = true, drag_selectable = true, alt_view_angle = true,
  hide_when_face_down = true, ignore_fog_of_war = true, mass = true, drag = true, angular_drag = true,
  bounciness = true, static_friction = true, dynamic_friction = true, value = true, value_flags = true,
  grid_projection = true, measure_movement = true, use_rotation_value_flip = true, held_reduce_force = true,
  held_spin_index = true, held_flip_index = true, show_grid_projection = true, held_position_offset = true,
  held_rotation_offset = true, max_typed_number = true,
}

local methods = {}
E.methods = methods

local function st_(o)
  local st = S[o]
  if not st then error("not a TTS object", 3) end
  return st
end

local function requireAlive(o, name)
  local st = st_(o)
  if st.removed then
    E.destroyedAccess = (E.destroyedAccess or 0) + 1
    E.warn(string.format("%s.%s on a destroyed object (%s)\n%s", st.data.Nickname or st.data.Name, name,
      st.guid, debug.traceback("", 3)))
    return nil
  end
  return st
end

local objectMeta = {}
objectMeta.__index = function(o, k)
  local st = S[o]
  local m = methods[k]
  if m then
    local cache = st.bound
    local f = cache[k]
    if not f then
      f = function(a, ...)
        local s2 = S[o]
        if s2.removed and k ~= "isDestroyed" and k ~= "getGUID" then
          requireAlive(o, k)
          return nil
        end
        if a == o then return m(o, ...) end
        return m(o, a, ...)
      end
      cache[k] = f
    end
    return f
  end
  if k == "guid" then return st.guid end
  if k == "type" or k == "tag" then return typeOf(st.data.Name) end
  if k == "name" then return st.data.Name end
  if k == "script_state" then return E.stateOf(o) end
  if k == "script_code" then return st.data.LuaScript or "" end
  if k == "memo" then return st.data.Memo end
  if k == "is_face_down" then
    local z = st.rot.z % 360
    return z > 90 and z < 270
  end
  if k == "locked" then return st.locked end
  if k == "resting" then return st.resting end
  if k == "spawning" then return st.spawning end
  if k == "loading_custom" then return false end
  if k == "interactable" then
    if st.props.interactable == nil then return true end
    return st.props.interactable
  end
  if k == "remainder" then return st.remainder end
  if k == "held_by_color" then return nil end
  if k == "UI" then return st.ui end
  if k == "Book" then
    if st.data.Name == "Custom_PDF" then return st.book end
    return nil
  end
  if k == "TextTool" then
    if st.data.Name == "3DText" then return st.textTool end
    return nil
  end
  if k == "Counter" or k == "Clock" or k == "LayoutZone" or k == "RPGFigurine" or k == "Browser"
     or k == "AssetBundle" or k == "Container" then
    return nil
  end
  if st.props[k] ~= nil then return st.props[k] end
  if SETTABLE[k] then
    if k == "use_gravity" or k == "use_snap_points" or k == "use_hands" then return true end
    return nil
  end
  local key = typeOf(st.data.Name) .. "." .. tostring(k)
  E.gaps[key] = (E.gaps[key] or 0) + 1
  return nil
end
objectMeta.__newindex = function(o, k, v)
  local st = S[o]
  if k == "memo" then st.data.Memo = v
  elseif k == "script_state" then st.data.LuaScriptState = v
  elseif k == "script_code" then st.data.LuaScript = v
  elseif k == "resting" then st.resting = v
  else st.props[k] = v end
end
objectMeta.__tostring = function(o)
  local st = S[o]
  return string.format("%s(%s)", tostring(st.data.Nickname or st.data.Name), tostring(st.guid))
end

function E.stateOf(o)
  local st = S[o]
  if st.env and type(rawget(st.env, "onSave")) == "function" then
    local ok, v = callIn({ env = st.env, who = st.env.__who }, "onSave")
    if ok then
      if v ~= nil then st.data.LuaScriptState = v end
      return v or ""
    end
  end
  return st.data.LuaScriptState or ""
end

local function entryOf(c, i)
  return { index = i - 1, name = c.Nickname or "", nickname = c.Nickname or "", guid = c.GUID or "",
           gm_notes = c.GMNotes or "", description = c.Description or "", memo = c.Memo,
           tags = datacopy(c.Tags or {}), lua_script = c.LuaScript or "",
           lua_script_state = c.LuaScriptState or "" }
end

-- identity / text
function methods.getGUID(o) return S[o].guid end
function methods.getName(o) return S[o].data.Nickname or "" end
function methods.setName(o, n) S[o].data.Nickname = n ; return true end
function methods.getDescription(o) return S[o].data.Description or "" end
function methods.setDescription(o, s) S[o].data.Description = s ; return true end
function methods.getGMNotes(o) return S[o].data.GMNotes or "" end
function methods.setGMNotes(o, s) S[o].data.GMNotes = s ; return true end
function methods.getMemo(o) return S[o].data.Memo end
function methods.setMemo(o, s) S[o].data.Memo = s ; return true end
function methods.getLuaScript(o) return S[o].data.LuaScript or "" end
function methods.setLuaScript(o, s) S[o].data.LuaScript = s ; return true end
function methods.getColorTint(o)
  local c = S[o].data.ColorDiffuse or {}
  return Color(c.r or 1, c.g or 1, c.b or 1, c.a or 1)
end
function methods.setColorTint(o, c) S[o].data.ColorDiffuse = { r = c.r or c[1], g = c.g or c[2], b = c.b or c[3], a = c.a or c[4] } ; return true end
function methods.isDestroyed(o) return S[o].removed == true end
function methods.getValue(o)
  local st = S[o]
  if st.data.Name == "3DText" then return (st.data.Text or {}).Text or "" end
  return st.props.value
end
function methods.setValue(o, v)
  local st = S[o]
  if st.data.Name == "3DText" then st.data.Text = st.data.Text or {} ; st.data.Text.Text = v
  else st.props.value = v end
  return true
end

-- tags
function methods.getTags(o) local l = {} for t in pairs(S[o].tags) do l[#l + 1] = t end table.sort(l) return l end
function methods.setTags(o, l) S[o].tags = {} for _, t in ipairs(l or {}) do S[o].tags[t] = true end return true end
function methods.addTag(o, t) S[o].tags[t] = true ; return true end
function methods.removeTag(o, t) S[o].tags[t] = nil ; return true end
function methods.hasTag(o, t) return S[o].tags[t] == true end
function methods.hasAnyTag(o) return next(S[o].tags) ~= nil end
function methods.hasMatchingTag(o, other)
  for t in pairs(S[o].tags) do if S[other] and S[other].tags[t] then return true end end
  return false
end

-- transform
function methods.getPosition(o) return Vector(S[o].pos) end
function methods.getRotation(o) return Vector(S[o].rot) end
function methods.getScale(o) return Vector(S[o].scale) end
-- a moved or flipped object leaves what it rested on (TTS lifts it; the
-- landing fires onCollisionEnter again)
local function liftOff(o)
  local st = S[o]
  local before = st.contacts
  if not before or st.locked then return end
  st.contacts = {}
  for other in pairs(before) do
    if isAlive(other) then
      collide(other, o, "onCollisionExit")
      collide(o, other, "onCollisionExit")
    end
  end
end
local function moved(o, frames)
  liftOff(o)
  updateZones(o)
  scheduleLanding(o, frames)
end
function methods.setPosition(o, p)
  local st = S[o]
  local v = vecOf(p)
  st.pos = { x = v.x, y = v.y, z = v.z }
  moved(o, 6)
  return true
end
function methods.setPositionSmooth(o, p)
  local st = S[o]
  local v = vecOf(p)
  st.smoothUntil = E.frame + 20
  st.pos = { x = v.x, y = v.y, z = v.z }
  moved(o, 24)
  return true
end
local function faceDown(rot) local z = rot.z % 360 return z > 90 and z < 270 end
function methods.setRotation(o, r)
  local st = S[o]
  local v = vecOf(r)
  local turned = faceDown(st.rot) ~= faceDown(v)
  st.rot = { x = v.x, y = v.y, z = v.z }
  if turned then liftOff(o) end
  scheduleLanding(o, 4)
  return true
end
function methods.setRotationSmooth(o, r) return methods.setRotation(o, r) end
function methods.setScale(o, s) local v = vecOf(s) S[o].scale = { x = v.x, y = v.y, z = v.z } ; return true end
function methods.scale(o, s)
  local st = S[o]
  if type(s) == "number" then s = { s, s, s } end
  local v = vecOf(s)
  st.scale = { x = st.scale.x * v.x, y = st.scale.y * v.y, z = st.scale.z * v.z }
  return true
end
function methods.translate(o, d)
  local v = vecOf(d)
  local st = S[o]
  return methods.setPosition(o, { st.pos.x + v.x, st.pos.y + v.y, st.pos.z + v.z })
end
function methods.rotate(o, d)
  local v = vecOf(d)
  local st = S[o]
  return methods.setRotation(o, { st.rot.x + v.x, st.rot.y + v.y, st.rot.z + v.z })
end
function methods.isSmoothMoving(o) return (S[o].smoothUntil or -1) > E.frame end
function methods.positionToWorld(o, p)
  local st = S[o]
  local v = vecOf(p)
  local x, y, z = rotate({ x = v.x * st.scale.x, y = v.y * st.scale.y, z = v.z * st.scale.z }, st.rot)
  return Vector(st.pos.x + x, st.pos.y + y, st.pos.z + z)
end
function methods.positionToLocal(o, p)
  local st = S[o]
  local v = vecOf(p)
  local x, y, z = unrotate({ x = v.x - st.pos.x, y = v.y - st.pos.y, z = v.z - st.pos.z }, st.rot)
  return Vector(x / st.scale.x, y / st.scale.y, z / st.scale.z)
end
function methods.getTransformForward(o) local x, y, z = rotate({ x = 0, y = 0, z = 1 }, S[o].rot) return Vector(x, y, z) end
function methods.getTransformRight(o) local x, y, z = rotate({ x = 1, y = 0, z = 0 }, S[o].rot) return Vector(x, y, z) end
function methods.getTransformUp(o) local x, y, z = rotate({ x = 0, y = 1, z = 0 }, S[o].rot) return Vector(x, y, z) end
function methods.getBounds(o)
  local b = aabb(o)
  return { center = Vector(b.center), size = Vector(b.size), offset = Vector(0, 0, 0) }
end
function methods.getBoundsNormalized(o)
  local st = S[o]
  local lx, ly, lz = localSize(o)
  return { center = Vector(st.pos), size = Vector(lx * st.scale.x, ly * st.scale.y, lz * st.scale.z),
           offset = Vector(0, 0, 0) }
end
methods.getVisualBoundsNormalized = methods.getBoundsNormalized
function methods.flip(o)
  local st = S[o]
  st.rot = { x = st.rot.x, y = st.rot.y, z = (st.rot.z + 180) % 360 }
  liftOff(o)
  scheduleLanding(o, 10)
  return true
end
function methods.getLock(o) return S[o].locked end
function methods.setLock(o, v)
  local st = S[o]
  st.locked = v and true or false
  if not st.locked then scheduleLanding(o, 4) end
  return true
end
function methods.getVelocity() return Vector(0, 0, 0) end
function methods.getAngularVelocity() return Vector(0, 0, 0) end
function methods.setVelocity() return true end
function methods.setAngularVelocity() return true end
function methods.addForce() return true end
function methods.addTorque() return true end
function methods.getMass(o) return S[o].props.mass or 1 end
function methods.registerCollisions() return true end
function methods.unregisterCollisions() return true end
function methods.getZones(o) local l = {} for z in pairs(S[o].zones or {}) do if isAlive(z) then l[#l + 1] = z end end return l end
function methods.randomize(o) return true end
function methods.roll(o) return true end
function methods.getRotationValue(o) return S[o].props.rotation_value end
function methods.setRotationValue(o, v) S[o].props.rotation_value = v ; return true end
function methods.getRotationValues(o) return datacopy(S[o].data.RotationValues or {}) end
function methods.setRotationValues(o, v) S[o].data.RotationValues = datacopy(v) ; return true end
function methods.getSelectingPlayers() return {} end
function methods.getFogOfWarReveal() return {} end
function methods.getJoints() return {} end
function methods.jointTo() return true end

-- highlight / visuals (tracked)
function methods.highlightOn(o, c, secs) S[o].highlight = c or true ; return true end
function methods.highlightOff(o) S[o].highlight = nil ; return true end
function methods.getDecals(o) return datacopy(S[o].data.AttachedDecals or {}) end
function methods.setDecals(o, l) S[o].data.AttachedDecals = datacopy(l or {}) ; return true end
function methods.addDecal(o, d) local l = S[o].data.AttachedDecals or {} l[#l + 1] = datacopy(d) S[o].data.AttachedDecals = l return true end
function methods.getVectorLines(o) return datacopy(S[o].props.__lines or {}) end
function methods.setVectorLines(o, l) S[o].props.__lines = datacopy(l or {}) ; return true end
function methods.getSnapPoints(o) return datacopy(S[o].data.AttachedSnapPoints or {}) end
function methods.setSnapPoints(o, l) S[o].data.AttachedSnapPoints = datacopy(l or {}) ; return true end
function methods.setHiddenFrom() return true end
function methods.setInvisibleTo() return true end
function methods.attachHider() return true end
function methods.getCustomObject(o)
  local d = S[o].data
  local c = d.CustomImage or d.CustomMesh or d.CustomPDF or {}
  local out = datacopy(c)
  if d.CustomImage then out.image = c.ImageURL ; out.image_secondary = c.ImageSecondaryURL end
  if d.CustomMesh then out.mesh = c.MeshURL ; out.diffuse = c.DiffuseURL end
  if d.CustomPDF then out.url = c.PDFUrl end
  if d.CustomDeck then
    local _, cd = next(d.CustomDeck)
    if cd then out.face = cd.FaceURL ; out.back = cd.BackURL ; out.width = cd.NumWidth ; out.height = cd.NumHeight end
  end
  return out
end
function methods.setCustomObject(o, p)
  local d = S[o].data
  if d.CustomImage then
    d.CustomImage.ImageURL = p.image or d.CustomImage.ImageURL
    d.CustomImage.ImageSecondaryURL = p.image_secondary or d.CustomImage.ImageSecondaryURL
  elseif d.CustomMesh then
    d.CustomMesh.MeshURL = p.mesh or d.CustomMesh.MeshURL
    d.CustomMesh.DiffuseURL = p.diffuse or d.CustomMesh.DiffuseURL
  end
  return true
end

-- buttons / inputs / menus
local BUTTON_DEFAULTS = { label = "", position = { 0, 0, 0 }, rotation = { 0, 0, 0 }, scale = { 1, 1, 1 },
  width = 100, height = 100, font_size = 100, tooltip = "" }
local function withIndex(list)
  if #list == 0 then return nil end
  local l = {}
  for i, b in ipairs(list) do
    local c = datacopy(b)
    c.function_owner = b.function_owner
    c.index = i - 1
    l[i] = c
  end
  return l
end
function methods.getButtons(o) return withIndex(S[o].buttons) end
function methods.createButton(o, def)
  if type(def) ~= "table" or def.click_function == nil then error("createButton: click_function is required") end
  local b = {}
  for k, v in pairs(BUTTON_DEFAULTS) do b[k] = datacopy(v) end
  for k, v in pairs(def) do b[k] = (k == "function_owner") and v or datacopy(v) end
  b.function_owner = def.function_owner or (currentWho and currentWho.self) or o
  table.insert(S[o].buttons, b)
  return true
end
function methods.editButton(o, p)
  local b = S[o].buttons[(p.index or 0) + 1]
  if not b then error("editButton: no button " .. tostring(p.index)) end
  for k, v in pairs(p) do if k ~= "index" then b[k] = (k == "function_owner") and v or datacopy(v) end end
  return true
end
function methods.removeButton(o, i)
  if not S[o].buttons[(i or 0) + 1] then error("removeButton: no button " .. tostring(i)) end
  table.remove(S[o].buttons, (i or 0) + 1)
  return true
end
function methods.clearButtons(o) S[o].buttons = {} ; return true end
function methods.getInputs(o) return withIndex(S[o].inputs) end
function methods.createInput(o, def)
  if type(def) ~= "table" or def.input_function == nil then error("createInput: input_function is required") end
  local b = {}
  for k, v in pairs(def) do b[k] = (k == "function_owner") and v or datacopy(v) end
  b.function_owner = def.function_owner or (currentWho and currentWho.self) or o
  b.value = b.value or ""
  table.insert(S[o].inputs, b)
  return true
end
function methods.editInput(o, p)
  local b = S[o].inputs[(p.index or 0) + 1]
  if not b then error("editInput: no input " .. tostring(p.index)) end
  for k, v in pairs(p) do if k ~= "index" then b[k] = v end end
  return true
end
function methods.removeInput(o, i) table.remove(S[o].inputs, (i or 0) + 1) ; return true end
function methods.clearInputs(o) S[o].inputs = {} ; return true end
function methods.addContextMenuItem(o, label, fn, keep)
  table.insert(S[o].menu, { label = label, fn = fn, owner = currentWho })
  return true
end
function methods.clearContextMenu(o) S[o].menu = {} ; return true end

-- script vars
function methods.getVar(o, k) local env = S[o].env return env and rawget(env, k) end
function methods.setVar(o, k, v) local env = S[o].env if env then rawset(env, k, v) end return true end
function methods.getTable(o, k) local env = S[o].env local v = env and rawget(env, k) return type(v) == "table" and v or nil end
function methods.setTable(o, k, v) local env = S[o].env if env then rawset(env, k, v) end return true end
function methods.call(o, name, param)
  local st = S[o]
  local fn = st.env and rawget(st.env, name)
  if type(fn) ~= "function" then
    E.warn(string.format("call(%s) on %s: no such function", tostring(name), tostring(o)))
    return nil
  end
  local prev = currentWho
  currentWho = st.env.__who
  local res = { xpcall(function() return fn(param) end, traceback) }
  currentWho = prev
  if not res[1] then error(res[2], 0) end
  return unpack(res, 2)
end

-- states
function methods.getStateId(o) return S[o].stateId end
function methods.getStates(o)
  local l = {}
  for id, d in pairs(S[o].states or {}) do
    l[#l + 1] = { id = tonumber(id), name = d.Nickname or "", guid = d.GUID or "", description = d.Description or "" }
  end
  table.sort(l, function(a, b) return a.id < b.id end)
  return l
end
function methods.setState(o, id)
  local st = S[o]
  local states = st.states
  if not states or not states[tostring(id)] then error("setState: no state " .. tostring(id)) end
  if tonumber(id) == st.stateId then return o end
  local cur = methods.getData(o)
  cur.States = nil
  local nxt = datacopy(states[tostring(id)])
  nxt.States = {}
  for k, d in pairs(states) do if k ~= tostring(id) then nxt.States[k] = datacopy(d) end end
  nxt.States[tostring(st.stateId)] = cur
  nxt.Transform = cur.Transform
  -- each state keeps its own GUID (TTS swaps the whole object)
  methods.destruct(o, true)
  removeNow(o)
  local n = makeObject(nxt, tonumber(id), { origin = st.origin })
  E.fire("onObjectStateChange", n, st.guid)
  return n
end

-- data
function methods.getData(o)
  local st = S[o]
  local d = datacopy(st.data)
  d.GUID = st.guid
  if st.contained then d.ContainedObjects = datacopy(st.contained) end
  d.LuaScriptState = E.stateOf(o)
  local tags = methods.getTags(o)
  d.Tags = #tags > 0 and tags or nil
  d.Locked = st.locked
  d.Transform = { posX = st.pos.x, posY = st.pos.y, posZ = st.pos.z, rotX = st.rot.x, rotY = st.rot.y,
                  rotZ = st.rot.z, scaleX = st.scale.x, scaleY = st.scale.y, scaleZ = st.scale.z }
  if st.states then d.States = datacopy(st.states) end
  if st.buttons and #st.buttons > 0 then end
  return d
end
function methods.getJSON(o) return J.encode(methods.getData(o)) end

-- lifecycle
function removeNow(o)
  local st = S[o]
  if st.removed then return end
  st.removed = true
  byGuid[st.guid] = nil
  for i, x in ipairs(E.objects) do if x == o then table.remove(E.objects, i) break end end
end
E.removeNow = removeNow

function methods.destruct(o, silent)
  local st = S[o]
  if st.destroying or st.removed then return true end
  st.destroying = true
  if not silent then E.fire("onObjectDestroy", o) end
  pendingDestroy[#pendingDestroy + 1] = o
  return true
end
function methods.reload(o)
  local d = methods.getData(o)
  local st = S[o]
  methods.destruct(o)
  removeNow(o)
  return makeObject(d, st.stateId > 0 and st.stateId or nil, { keepGuid = true, origin = st.origin })
end
function methods.clone(o, p)
  p = p or {}
  local d = methods.getData(o)
  d.GUID = nil
  local pos = vecOf(p.position) or { x = S[o].pos.x + 1, y = S[o].pos.y + 1, z = S[o].pos.z }
  return spawnData(d, { position = pos, rotation = p.rotation }, S[o].origin)
end

-- containers
function methods.getObjects(o)
  local st = S[o]
  if st.contained then
    local l = {}
    for i, c in ipairs(st.contained) do l[i] = entryOf(c, i) end
    return l
  end
  if isZone(o) then
    local l = {}
    local b = aabb(o)
    for _, x in ipairs(E.objects) do
      if x ~= o and not S[x].removed and not isZone(x) and containsXYZ(b, S[x].pos) then l[#l + 1] = x end
    end
    return l
  end
  return {}
end
function methods.getQuantity(o) local c = S[o].contained return c and #c or -1 end
function methods.shuffle(o)
  local c = S[o].contained
  if c then
    for i = #c, 2, -1 do
      local j = math.floor(rand() * i) + 1
      c[i], c[j] = c[j], c[i]
    end
    S[o].shuffled = (S[o].shuffled or 0) + 1
  end
  return true
end
function methods.reset(o)
  local st = S[o]
  if typeOf(st.data.Name) == "Bag" or typeOf(st.data.Name) == "Infinite" then st.contained = {} end
  return true
end
local function deckIds(st)
  local ids = {}
  for _, c in ipairs(st.contained or {}) do ids[#ids + 1] = c.CardID or 0 end
  st.data.DeckIDs = ids
  local cd = {}
  for _, c in ipairs(st.contained or {}) do
    for k, v in pairs(c.CustomDeck or {}) do cd[k] = v end
  end
  if next(cd) then st.data.CustomDeck = datacopy(cd) end
end

function methods.takeObject(o, p)
  p = p or {}
  local st = S[o]
  local c = st.contained
  if not c then error("takeObject: " .. tostring(o) .. " is not a container") end
  if #c == 0 then return nil end
  local idx = (p.index or 0) + 1
  if p.top == false then idx = #c end
  if p.guid then
    idx = nil
    for i, x in ipairs(c) do if x.GUID == p.guid then idx = i end end
    if not idx then error("takeObject: no object with guid " .. tostring(p.guid) .. " in " .. tostring(o)) end
  end
  local cd = table.remove(c, idx)
  if not cd then return nil end
  local isDeck = typeOf(st.data.Name) == "Deck"
  if isDeck then deckIds(st) end
  cd = datacopy(cd)
  cd.Transform = cd.Transform or {}
  local pos = vecOf(p.position)
  if not pos then
    if isDeck then
      local x, y, z = rotate({ x = 0, y = 0, z = 0 }, st.rot)
      pos = { x = st.pos.x + x, y = st.pos.y + 1, z = st.pos.z + z }
    else
      pos = { x = st.pos.x, y = st.pos.y + 2, z = st.pos.z }
    end
  end
  cd.Transform.posX, cd.Transform.posY, cd.Transform.posZ = pos.x, pos.y, pos.z
  local rot = vecOf(p.rotation)
  if rot then
    cd.Transform.rotX, cd.Transform.rotY, cd.Transform.rotZ = rot.x, rot.y, rot.z
  elseif isDeck then
    cd.Transform.rotX, cd.Transform.rotY, cd.Transform.rotZ = st.rot.x, st.rot.y, st.rot.z
  end
  local child = makeObject(cd, nil, { origin = st.origin, deferScript = true })
  S[child].cameFrom = o   -- it does not drop straight back into what it left
  E.fire("onObjectLeaveContainer", o, child)
  if isDeck and #c == 0 then
    methods.destruct(o, true)
    removeNow(o)
  elseif isDeck and #c == 1 then
    -- the last card is no longer a deck (TTS "remainder")
    local last = datacopy(c[1])
    last.Transform = { posX = st.pos.x, posY = st.pos.y, posZ = st.pos.z, rotX = st.rot.x, rotY = st.rot.y,
                       rotZ = st.rot.z, scaleX = (last.Transform or {}).scaleX or 1, scaleY = 1,
                       scaleZ = (last.Transform or {}).scaleZ or 1 }
    st.contained = {}
    local rem = makeObject(last, nil, { origin = st.origin, deferScript = true })
    st.remainder = rem
    methods.destruct(o, true)
    removeNow(o)
  end
  scheduleLanding(child, p.smooth == false and 4 or 18)
  if p.callback_function then
    local owner = who()
    addTimer({ frame = E.frame + 3, fn = function() p.callback_function(child, p.params) end, owner = owner })
  end
  return child
end

function E.putInto(container, obj)
  local cs = S[container]
  local ctype = typeOf(cs.data.Name)
  local d = methods.getData(obj)
  S[obj].inContainer = container
  -- the entered object stays readable while onObjectEnterContainer runs
  -- (TTS removes it right after); it is no longer on the table meanwhile
  S[obj].landFrame = nil
  local function gone() removeNow(obj) end
  if ctype == "Card" then
    -- card on card: a new deck at the container's spot
    local base = methods.getData(container)
    methods.destruct(container, true)
    removeNow(container)
    local deck = { Name = "Deck", Nickname = "", Transform = base.Transform, ContainedObjects = {},
                   Tags = nil, DeckIDs = {} }
    local function push(x)
      if typeOf(x.Name) == "Deck" then
        for _, cc in ipairs(x.ContainedObjects or {}) do table.insert(deck.ContainedObjects, cc) end
      else
        x.Transform = nil
        table.insert(deck.ContainedObjects, x)
      end
    end
    push(d) ; push(base)
    local nd = makeObject(deck, nil, { origin = cs.origin })
    deckIds(S[nd])
    E.fire("onObjectEnterContainer", nd, obj)
    gone()
    return nd
  end
  if not cs.contained then error("putObject: " .. tostring(container) .. " is not a container") end
  if typeOf(d.Name) == "Deck" and ctype == "Deck" then
    for i = #(d.ContainedObjects or {}), 1, -1 do table.insert(cs.contained, 1, d.ContainedObjects[i]) end
  elseif ctype == "Deck" then
    d.Transform = nil
    table.insert(cs.contained, 1, d)
  else
    table.insert(cs.contained, d)
  end
  if ctype == "Deck" then deckIds(cs) end
  E.fire("onObjectEnterContainer", container, obj)
  gone()
  return container
end

function methods.putObject(o, other)
  if not S[other] or S[other].removed then return nil end
  if not mayEnter(o, other) then return nil end
  return E.putInto(o, other)
end
function methods.deal(o, n, color)
  for _ = 1, n or 1 do
    local c = methods.takeObject(o, { position = { 0, 3, -30 } })
    if not c then break end
    S[c].hand = color or "White"
  end
  return true
end
function methods.dealToColorWithOffset(o, off, flip, color)
  return methods.takeObject(o, { position = { 0, 3, -30 } })
end
function methods.cut(o) return nil end
function methods.split(o) return nil end
function methods.spread(o) return nil end

-- attachments (none are modelled)
function methods.getAttachments() return {} end
function methods.removeAttachment() return nil end
function methods.removeAttachments() return {} end
function methods.destroyAttachments() return true end
function methods.addAttachment() return true end

------------------------------------------------------------------ making --

local function envFor(o, st, label, origin)
  local env = {}
  env.self = o
  env._G = env
  env.__who = { label = label, origin = origin, self = o, env = env }
  env.require = E.makeRequire(env)
  setmetatable(env, { __index = E.G })
  return env
end

function makeObject(data, stateId, opts)
  opts = opts or {}
  local o = setmetatable({}, objectMeta)
  local guid = newGuid(data.GUID)
  local st = { data = data, buttons = {}, inputs = {}, menu = {}, tags = {}, props = {}, bound = {},
               guid = guid, locked = data.Locked == true, resting = true, spawning = true,
               origin = opts.origin or "table" }
  S[o] = st
  data.GUID = guid
  for _, t in ipairs(data.Tags or {}) do st.tags[t] = true end
  data.Tags = nil
  local t = data.Transform or {}
  st.pos = { x = t.posX or 0, y = t.posY or 0, z = t.posZ or 0 }
  st.rot = { x = t.rotX or 0, y = t.rotY or 0, z = t.rotZ or 0 }
  st.scale = { x = t.scaleX or 1, y = t.scaleY or 1, z = t.scaleZ or 1 }
  data.Transform = nil
  st.states = data.States
  data.States = nil
  st.stateId = st.states and (stateId or 1) or -1
  local ty = typeOf(data.Name)
  if ty == "Bag" or ty == "Infinite" or ty == "Deck" then
    st.contained = data.ContainedObjects or {}
  end
  data.ContainedObjects = nil
  st.ui = makeUI(tostring(data.Nickname))
  st.book = { page = 0 }
  st.book.getPage = function() return st.book.page end
  st.book.setPage = function(p) st.book.page = p ; return true end
  st.book.setHighlight = function() return true end
  st.book.clearHighlight = function() return true end
  st.textTool = {
    getValue = function() return (data.Text or {}).Text or "" end,
    setValue = function(v) data.Text = data.Text or {} ; data.Text.Text = v ; return true end,
    getFontSize = function() return (data.Text or {}).fontSize or 64 end,
    setFontSize = function(v) data.Text = data.Text or {} ; data.Text.fontSize = v ; return true end,
    getFontColor = function() return Color(1, 1, 1) end,
    setFontColor = function() return true end,
  }
  byGuid[guid] = o
  E.objects[#E.objects + 1] = o
  st.label = string.format("%s [%s]", tostring(data.Nickname ~= "" and data.Nickname or data.Name), guid)
  if opts.noScript then return o end
  if opts.immediate then
    loadScript(o)
  else
    pendingLoad[#pendingLoad + 1] = o
  end
  return o
end
E.makeObject = makeObject

function loadScript(o, savedOverride)
  local st = S[o]
  if st.removed or st.loaded then return end
  st.loaded = true
  local data = st.data
  if data.LuaScript and data.LuaScript ~= "" then
    local env = envFor(o, st, st.label, st.origin)
    st.env = env
    local chunk, err = load(data.LuaScript, "=" .. st.label, "t", env)
    if not chunk then
      E.protect(env.__who, error, err)
    else
      local prev = currentWho
      currentWho = env.__who
      local ok = E.protect(env.__who, chunk)
      if ok and type(rawget(env, "onLoad")) == "function" then
        E.protect(env.__who, env.onLoad, savedOverride or data.LuaScriptState or "")
      end
      currentWho = prev
    end
  end
  st.spawning = false
  E.fire("onObjectSpawn", o)
end
E.loadScript = loadScript

function spawnData(data, p, origin)
  p = p or {}
  data = datacopy(data)
  data.Transform = data.Transform or {}
  local pos, rot = vecOf(p.position), vecOf(p.rotation)
  if pos then data.Transform.posX, data.Transform.posY, data.Transform.posZ = pos.x, pos.y, pos.z end
  if rot then data.Transform.rotX, data.Transform.rotY, data.Transform.rotZ = rot.x, rot.y, rot.z end
  local sc = vecOf(p.scale)
  if sc then data.Transform.scaleX, data.Transform.scaleY, data.Transform.scaleZ = sc.x, sc.y, sc.z end
  local o = makeObject(data, nil, { origin = origin or (currentWho and currentWho.origin) or "table" })
  updateZones(o)
  scheduleLanding(o, 10)
  if p.callback_function then
    local owner = who()
    addTimer({ frame = E.frame + 3, fn = function() p.callback_function(o, p.params) end, owner = owner })
  end
  return o
end
E.spawnData = spawnData

------------------------------------------------------------------ require --

local moduleCache = setmetatable({}, { __mode = "k" })
local sourceCache = {}
local function findModule(name)
  if sourceCache[name] ~= nil then return sourceCache[name] end
  for _, dir in ipairs(E.srcDirs) do
    for _, ext in ipairs({ ".ttslua", ".lua" }) do
      local path = dir .. "/" .. name .. ext
      local f = io.open(path, "rb")
      if f then
        local src = f:read("*a")
        f:close()
        sourceCache[name] = { src = src, path = path }
        return sourceCache[name]
      end
    end
  end
  sourceCache[name] = false
  return false
end

function E.makeRequire(env)
  return function(name)
    local cache = moduleCache[env]
    if not cache then cache = {} ; moduleCache[env] = cache end
    if cache[name] ~= nil then return cache[name] end
    local m = findModule(name)
    if not m then error("module '" .. tostring(name) .. "' not found", 2) end
    local chunk, err = load(m.src, "=" .. name, "t", env)
    if not chunk then error(err, 2) end
    local res = chunk()
    if res == nil then res = true end
    cache[name] = res
    return res
  end
end

------------------------------------------------------------------ Global --

local players = {}
local PLAYER_COLORS = { "White", "Brown", "Red", "Orange", "Yellow", "Green", "Teal", "Blue", "Purple", "Pink", "Grey", "Black" }
E.seated = { White = true }
local function playerFor(color)
  if players[color] then return players[color] end
  local p = { color = color, steam_name = color == "White" and "Tester" or "", steam_id = "0",
              host = color == "White", admin = color == "White", promoted = false, team = "None",
              blindfolded = false }
  local mt = { __index = function(_, k)
    if k == "seated" then return E.seated[color] == true end
    return nil
  end }
  setmetatable(p, mt)
  p.getHandObjects = function() return {} end
  p.getHandCount = function() return 1 end
  p.getHandTransform = function() return { position = Vector(0, 3, -30), rotation = Vector(0, 0, 0),
    scale = Vector(10, 5, 3), forward = Vector(0, 0, 1), right = Vector(1, 0, 0), up = Vector(0, 1, 0) } end
  p.getSelectedObjects = function() return {} end
  p.clearSelectedObjects = function() return true end
  p.getHoverObject = function() return nil end
  p.getPointerPosition = function() return Vector(0, 1, 0) end
  p.getPointerRotation = function() return 0 end
  p.lookAt = function(t) p.lastLook = t ; return true end
  p.showConfirmDialog = function(msg) E.say("dialog", tostring(msg)) ; return true end
  p.showInputDialog = function(msg) E.say("dialog", tostring(msg)) ; return true end
  p.showInfoDialog = function(msg) E.say("dialog", tostring(msg)) ; return true end
  p.showOptionsDialog = function(msg) E.say("dialog", tostring(msg)) ; return true end
  p.showColorDialog = function() return true end
  p.showMemoDialog = function() return true end
  p.broadcast = function(msg) say("broadcast", tostring(msg)) ; return true end
  p.print = function(msg) say("print", tostring(msg)) ; return true end
  p.pingTable = function() return true end
  p.attachCameraToObject = function() return true end
  p.setCameraMode = function() return true end
  p.changeColor = function() return true end
  p.setHandTransform = function() return true end
  p.getHoldingObjects = function() return {} end
  players[color] = p
  return p
end

local PlayerApi = setmetatable({}, { __index = function(_, k)
  for _, c in ipairs(PLAYER_COLORS) do if c == k then return playerFor(c) end end
  return nil
end })
PlayerApi.getPlayers = function()
  local l = {}
  for _, c in ipairs(PLAYER_COLORS) do if E.seated[c] then l[#l + 1] = playerFor(c) end end
  return l
end
PlayerApi.getSpectators = function() return {} end
PlayerApi.getColors = function() return { unpack(PLAYER_COLORS) } end
PlayerApi.getAvailableColors = function() return { unpack(PLAYER_COLORS) } end

local function globalObject()
  local g = { guid = "-1" }
  local ui = makeUI("Global")
  g.UI = ui
  local snaps, lines, decals = {}, {}, {}
  g.getGUID = function() return "-1" end
  g.getName = function() return "Global" end
  g.getVar = function(k) return globalEnv and rawget(globalEnv, k) end
  g.setVar = function(k, v) if globalEnv then rawset(globalEnv, k, v) end return true end
  g.getTable = function(k) local v = globalEnv and rawget(globalEnv, k) return type(v) == "table" and v or nil end
  g.setTable = function(k, v) if globalEnv then rawset(globalEnv, k, v) end return true end
  g.call = function(name, param)
    local fn = globalEnv and rawget(globalEnv, name)
    if type(fn) ~= "function" then
      E.warn("Global.call(" .. tostring(name) .. "): no such function")
      return nil
    end
    local prev = currentWho
    currentWho = globalEnv.__who
    local res = { xpcall(function() return fn(param) end, traceback) }
    currentWho = prev
    if not res[1] then error(res[2], 0) end
    return unpack(res, 2)
  end
  g.getSnapPoints = function() return datacopy(snaps) end
  g.setSnapPoints = function(l) snaps = datacopy(l or {}) return true end
  g.getVectorLines = function() return datacopy(lines) end
  g.setVectorLines = function(l) lines = datacopy(l or {}) return true end
  g.getDecals = function() return datacopy(decals) end
  g.setDecals = function(l) decals = datacopy(l or {}) return true end
  g.addDecal = function(d) decals[#decals + 1] = datacopy(d) return true end
  g.getLuaScript = function() return E.globalScript or "" end
  g.setLuaScript = function(s) E.globalScript = s return true end
  setmetatable(g, {
    __index = function(_, k)
      if k == "script_state" then
        if globalEnv and type(rawget(globalEnv, "onSave")) == "function" then
          local ok, v = callIn({ env = globalEnv, who = globalEnv.__who }, "onSave")
          if ok then return v or "" end
        end
        return E.globalState or ""
      end
      return nil
    end,
    __newindex = function(t, k, v)
      if k == "script_state" then E.globalState = v else rawset(t, k, v) end
    end,
  })
  return g
end
GlobalObj = globalObject()
E.Global = GlobalObj

local function fmtArgs(...)
  local parts = {}
  for i = 1, select("#", ...) do parts[#parts + 1] = tostring((select(i, ...))) end
  return table.concat(parts, "\t")
end

local function webRequest(url, method, body)
  local req = { url = url, is_done = false, is_error = false, text = "", error = nil, response_code = 0,
                download_progress = 0, upload_progress = 0 }
  req.dispose = function() return true end
  req.getResponseHeader = function() return nil end
  req.getResponseHeaders = function() return {} end
  local fx = E.webFixtures and E.webFixtures[url]
  return req, fx
end
local function webCall(url, method, body, cb)
  local req, fx = webRequest(url, method, body)
  E.webRequests = E.webRequests or {}
  E.webRequests[#E.webRequests + 1] = { url = url, method = method }
  local owner = who()
  addTimer({ frame = E.frame + 2, owner = owner, fn = function()
    req.is_done = true
    req.download_progress = 1
    if fx then
      req.text, req.response_code = fx, 200
    else
      req.is_error, req.error, req.response_code = true, "offline (the emulator never uses the network)", 0
    end
    if cb then cb(req) end
  end })
  return req
end

local coroutines = {}

E.G = setmetatable({
  JSON = E.JSON,
  Wait = Wait,
  Global = GlobalObj,
  Vector = Vector,
  Color = Color,
  Physics = Physics,
  Player = PlayerApi,
  UI = GlobalObj.UI,
  unpack = unpack,
  loadstring = load,
  print = function(...) say("print", fmtArgs(...)) end,
  log = function(v, label) say("log", (label and (tostring(label) .. ": ") or "") .. (type(v) == "table" and J.encode(v) or tostring(v))) end,
  logString = function(v) return type(v) == "table" and J.encode(v) or tostring(v) end,
  logStyle = function() return true end,
  printToAll = function(msg) say("print", tostring(msg)) return true end,
  printToColor = function(msg) say("print", tostring(msg)) return true end,
  broadcastToAll = function(msg) say("broadcast", tostring(msg)) return true end,
  broadcastToColor = function(msg) say("broadcast", tostring(msg)) return true end,
  sendExternalMessage = function(t) E.external = E.external or {} ; E.external[#E.external + 1] = t ; return true end,
  stringColorToRGB = function(c) local col = Color.fromString(c) return col end,
  getObjects = function() local l = {} for _, o in ipairs(E.objects) do if not S[o].removed then l[#l + 1] = o end end return l end,
  getAllObjects = function() local l = {} for _, o in ipairs(E.objects) do if not S[o].removed then l[#l + 1] = o end end return l end,
  getObjectFromGUID = function(g) if g == nil then return nil end local o = byGuid[g] if o and not S[o].removed then return o end return nil end,
  getObjectsWithTag = function(tag)
    local l = {}
    for _, o in ipairs(E.objects) do if not S[o].removed and S[o].tags[tag] then l[#l + 1] = o end end
    return l
  end,
  getObjectsWithAnyTags = function(tags)
    local l = {}
    for _, o in ipairs(E.objects) do
      if not S[o].removed then
        for _, t in ipairs(tags or {}) do if S[o].tags[t] then l[#l + 1] = o break end end
      end
    end
    return l
  end,
  getObjectsWithAllTags = function(tags)
    local l = {}
    for _, o in ipairs(E.objects) do
      if not S[o].removed then
        local all = true
        for _, t in ipairs(tags or {}) do if not S[o].tags[t] then all = false end end
        if all then l[#l + 1] = o end
      end
    end
    return l
  end,
  getSeatedPlayers = function() local l = {} for _, c in ipairs(PLAYER_COLORS) do if E.seated[c] then l[#l + 1] = c end end return l end,
  destroyObject = function(o) return methods.destruct(o) end,
  spawnObjectJSON = function(p) return spawnData(J.decode(p.json), p) end,
  spawnObjectData = function(p) return spawnData(p.data, p) end,
  spawnObject = function(p)
    p = p or {}
    local d = { Name = p.type or "BlockSquare", Nickname = "", Transform = {} }
    return spawnData(d, p)
  end,
  group = function(objs) return objs end,
  copy = function() return true end,
  paste = function() return {} end,
  flipTable = function() return true end,
  clearPixelPaint = function() return true end,
  clearVectorPaint = function() return true end,
  getVectorLines = function() return GlobalObj.getVectorLines() end,
  setVectorLines = function(l) return GlobalObj.setVectorLines(l) end,
  getSnapPoints = function() return GlobalObj.getSnapPoints() end,
  setSnapPoints = function(l) return GlobalObj.setSnapPoints(l) end,
  addHotkey = function(name) E.hotkeys = E.hotkeys or {} ; E.hotkeys[#E.hotkeys + 1] = name ; return true end,
  addContextMenuItem = function() return true end,
  clearContextMenu = function() return true end,
  showHotkeyConfig = function() return true end,
  setLookingForPlayers = function() return true end,
  startLuaCoroutine = function(owner, fname)
    local env = (owner == GlobalObj or owner == nil) and globalEnv or (S[owner] and S[owner].env)
    local fn = env and rawget(env, fname)
    if type(fn) ~= "function" then error("startLuaCoroutine: no function " .. tostring(fname)) end
    local co = coroutine.create(fn)
    coroutines[#coroutines + 1] = { co = co, who = env.__who }
    return true
  end,
  WebRequest = {
    get = function(url, cb) return webCall(url, "GET", nil, cb) end,
    post = function(url, body, cb) return webCall(url, "POST", body, cb) end,
    put = function(url, body, cb) return webCall(url, "PUT", body, cb) end,
    delete = function(url, cb) return webCall(url, "DELETE", nil, cb) end,
    head = function(url, cb) return webCall(url, "HEAD", nil, cb) end,
    custom = function(url, method, download, body, headers, cb) return webCall(url, method, body, cb) end,
  },
  Hands = { enable = true, disable_unused = false, hiding = 1, getHands = function() return {} end },
  Turns = { enable = false, type = 1, order = {}, reverse_order = false, skip_empty_hands = true,
            disable_interactations = false, pass_turns = true, turn_color = "",
            getNextTurnColor = function() return "White" end, getPreviousTurnColor = function() return "White" end },
  Notes = (function()
    local notes, tabs = "", {}
    return {
      getNotes = function() return notes end,
      setNotes = function(s) notes = s or "" ; return true end,
      getNotebookTabs = function() return datacopy(tabs) end,
      addNotebookTab = function(p) tabs[#tabs + 1] = datacopy(p) ; return #tabs - 1 end,
      editNotebookTab = function(p) local t = tabs[(p.index or 0) + 1] if t then for k, v in pairs(p) do t[k] = v end end return true end,
      removeNotebookTab = function(i) table.remove(tabs, (i or 0) + 1) ; return true end,
    }
  end)(),
  Time = { fixed_delta_time = FRAME, delta_time = FRAME, time = 0 },
  Info = { name = "Arkham SCE", type = "", complexity = "", tags = {}, number_of_players = { 1, 4 },
           playing_time = { 60, 120 }, playtime = 0 },
  Grid = { type = 0, show_lines = false, color = Color(0, 0, 0), opacity = 0.75, thick_lines = false,
           snapping = 1, offsetX = 0, offsetY = 0, sizeX = 2, sizeY = 2 },
  Lighting = { light_intensity = 0.54, ambient_intensity = 1.3, apply = function() return true end,
               setLightColor = function() return true end, setAmbientSkyColor = function() return true end,
               setAmbientEquatorColor = function() return true end, setAmbientGroundColor = function() return true end,
               getLightColor = function() return Color(1, 1, 1) end },
  Tables = { getTable = function() return "Table_None" end, setTable = function() return true end,
             getTableObject = function() return nil end, getCustomURL = function() return "" end,
             setCustomURL = function() return true end },
  Backgrounds = { getBackground = function() return "" end, setBackground = function() return true end,
                  getCustomURL = function() return "" end, setCustomURL = function() return true end },
  MusicPlayer = { play = function() return true end, pause = function() return true end,
                  getCurrentAudioclip = function() return {} end, setCurrentAudioclip = function() return true end,
                  getPlaylist = function() return {} end, setPlaylist = function() return true end },
  Clock = {},
}, { __index = _G })

------------------------------------------------------------------ frames --

local function ownerGone(t)
  local selfObj = t.owner and t.owner.self
  return selfObj ~= nil and selfObj ~= GlobalObj and S[selfObj] ~= nil and S[selfObj].removed
end

local function runTimer(t)
  -- a destroyed object's script is gone, and its pending Waits with it
  if ownerGone(t) then E.droppedWaits = (E.droppedWaits or 0) + 1 return end
  local prev = currentWho
  currentWho = t.owner or currentWho
  E.protect(t.owner or { label = "timer", origin = "?" }, t.fn)
  currentWho = prev
end

local function flushDestroy()
  if #pendingDestroy == 0 then return end
  local list = pendingDestroy
  pendingDestroy = {}
  for _, o in ipairs(list) do removeNow(o) end
end

local function flushLoads()
  local guard = 0
  while #pendingLoad > 0 and guard < 50 do
    guard = guard + 1
    local list = pendingLoad
    pendingLoad = {}
    for _, o in ipairs(list) do loadScript(o) end
  end
end

--- Advance one frame: script loads, timers due, conditions, landings,
-- onUpdate, coroutines, then deferred destruction.
function E.step()
  E.frame = E.frame + 1
  E.now = E.frame * FRAME
  E.G.Time.time = E.now
  flushLoads()
  -- timers (a timer added this frame waits for the next one)
  local due = {}
  local keep = {}
  for _, t in ipairs(timers) do
    if cancelled[t.id] then
      -- dropped
    elseif t.cond then
      if t.frame <= E.frame then due[#due + 1] = t else keep[#keep + 1] = t end
    elseif (t.frame and t.frame <= E.frame) or (t.at and t.at <= E.now + 1e-9) then
      due[#due + 1] = t
    else
      keep[#keep + 1] = t
    end
  end
  timers = keep
  table.sort(due, function(a, b) return a.id < b.id end)
  for _, t in ipairs(due) do
    if ownerGone(t) then
      E.droppedWaits = (E.droppedWaits or 0) + 1
    elseif not cancelled[t.id] then
      if t.cond then
        local prev = currentWho
        currentWho = t.owner or currentWho
        local ok, v = E.protect(t.owner or { label = "condition", origin = "?" }, t.cond)
        currentWho = prev
        if ok and v then
          runTimer(t)
        elseif ok and t.deadline and E.now >= t.deadline then
          if t.timeoutFn then runTimer({ fn = t.timeoutFn, owner = t.owner }) end
        elseif ok then
          t.frame = E.frame + 1
          timers[#timers + 1] = t
        end
      else
        runTimer(t)
        if t.at and t.reps and (t.reps == -1 or t.reps > 1) then
          if t.reps > 1 then t.reps = t.reps - 1 end
          t.at = E.now + math.max(FRAME, t.every)
          timers[#timers + 1] = t
        end
      end
    end
  end
  -- landings
  for _, o in ipairs({ unpack(E.objects) }) do
    local st = S[o]
    if st and not st.removed and st.landFrame and st.landFrame <= E.frame then land(o) end
  end
  -- onUpdate (skipped unless enabled: SCED's per-frame work is not needed)
  if E.runOnUpdate then E.fire("onUpdate") end
  -- coroutines
  for i = #coroutines, 1, -1 do
    local c = coroutines[i]
    local prev = currentWho
    currentWho = c.who
    local ok, res = coroutine.resume(c.co)
    currentWho = prev
    if not ok then
      E.protect(c.who, error, res)
      table.remove(coroutines, i)
    elseif coroutine.status(c.co) == "dead" then
      table.remove(coroutines, i)
    end
  end
  flushDestroy()
end

--- True while anything is scheduled: timers, script loads, landings,
-- deferred destruction, coroutines.
function E.pendingWork()
  for _, t in ipairs(timers) do if not cancelled[t.id] then return true end end
  if #pendingLoad > 0 or #pendingDestroy > 0 or #coroutines > 0 then return true end
  for _, o in ipairs(E.objects) do
    local st = S[o]
    if st and not st.removed and st.landFrame then return true end
  end
  return false
end

function E.run(seconds)
  local target = E.now + (seconds or 0)
  while E.now < target - 1e-9 do E.step() end
end
function E.frames(n) for _ = 1, n or 1 do E.step() end end

--- Run until cond() is true (checked every frame) or timeout seconds pass.
function E.runUntil(cond, timeout)
  local deadline = E.now + (timeout or 10)
  while E.now < deadline do
    local ok, v = pcall(cond)
    if ok and v then return true end
    E.step()
  end
  local ok, v = pcall(cond)
  return ok and v and true or false
end

------------------------------------------------------------------ loading --

--- Load a saved game table {LuaScript=, LuaScriptState=, ObjectStates=[...]}
-- the way TTS loads a save: every object is created, Global's chunk runs,
-- every object's script chunk and onLoad(script_state) run in order, then
-- Global's onLoad(state).
function E.loadSave(save, origin)
  E.globalScript = save.LuaScript or ""
  E.globalState = save.LuaScriptState or ""
  if save.SnapPoints then GlobalObj.setSnapPoints(save.SnapPoints) end
  local created = {}
  for _, d in ipairs(save.ObjectStates or {}) do
    created[#created + 1] = makeObject(datacopy(d), nil, { noScript = true, origin = origin or "table" })
  end
  if E.globalScript ~= "" then
    globalEnv = {}
    globalEnv.self = GlobalObj
    globalEnv._G = globalEnv
    globalEnv.__who = { label = "Global", origin = origin or "table", self = GlobalObj, env = globalEnv }
    globalEnv.require = E.makeRequire(globalEnv)
    setmetatable(globalEnv, { __index = E.G })
    E.globalEnv = globalEnv
    local chunk, err = load(E.globalScript, "=Global", "t", globalEnv)
    if not chunk then E.protect(globalEnv.__who, error, err)
    else
      currentWho = globalEnv.__who
      E.protect(globalEnv.__who, chunk)
    end
  end
  -- object chunks first, then their onLoad (all scripts exist before any onLoad)
  for _, o in ipairs(created) do
    local st = S[o]
    st.loaded = true
    if st.data.LuaScript and st.data.LuaScript ~= "" then
      local env = envFor(o, st, st.label, st.origin)
      st.env = env
      local chunk, err = load(st.data.LuaScript, "=" .. st.label, "t", env)
      currentWho = env.__who
      if not chunk then E.protect(env.__who, error, err) else E.protect(env.__who, chunk) end
    end
  end
  for _, o in ipairs(created) do
    local st = S[o]
    if st.env and type(rawget(st.env, "onLoad")) == "function" then
      currentWho = st.env.__who
      E.protect(st.env.__who, st.env.onLoad, st.data.LuaScriptState or "")
    end
    st.spawning = false
  end
  for _, o in ipairs(created) do updateZones(o) end
  if globalEnv and type(rawget(globalEnv, "onLoad")) == "function" then
    currentWho = globalEnv.__who
    E.protect(globalEnv.__who, globalEnv.onLoad, E.globalState)
  end
  currentWho = { label = "harness", origin = "harness" }
  return created
end

--- The whole table as a save {LuaScript, LuaScriptState, ObjectStates}.
function E.save()
  local objs = {}
  for _, o in ipairs(E.objects) do
    if not S[o].removed then objs[#objs + 1] = methods.getData(o) end
  end
  return { LuaScript = E.globalScript, LuaScriptState = GlobalObj.script_state, ObjectStates = objs,
           SnapPoints = GlobalObj.getSnapPoints() }
end

--- Throw the table away (a fresh TTS instance), keeping reports.
function E.clearWorld()
  for _, o in ipairs(E.objects) do S[o].removed = true end
  E.objects = {}
  byGuid = {}
  timers = {}
  pendingDestroy, pendingLoad = {}, {}
  coroutines = {}
  globalEnv = nil
  E.globalEnv = nil
end

------------------------------------------------------------ player acts --

--- A player's button click: runs click_function(obj, color, alt) in the
-- function owner's script, as TTS does.
function E.click(o, which, color, alt)
  local st = S[o]
  local b
  for i, x in ipairs(st.buttons) do
    if (type(which) == "number" and i - 1 == which) or x.click_function == which
       or (type(which) == "string" and tostring(x.label):sub(1, #which) == which) then
      b = x
      break
    end
  end
  if not b then return false, "no button " .. tostring(which) .. " on " .. tostring(o) end
  local owner = b.function_owner
  local env
  if owner == GlobalObj then env = globalEnv
  elseif owner ~= nil and S[owner] then env = S[owner].env
  else env = st.env end
  if not env then return false, "button owner has no script" end
  local fn = rawget(env, b.click_function)
  if type(fn) ~= "function" then return false, "no click function " .. tostring(b.click_function) end
  local prev = currentWho
  currentWho = env.__who
  local ok, res = E.protect(env.__who, fn, o, color or "White", alt and true or false)
  currentWho = prev
  return ok, res
end

--- A player typing into an input field.
function E.type(o, index, value, color)
  local st = S[o]
  local b = st.inputs[(index or 0) + 1]
  if not b then return false, "no input" end
  b.value = value
  local env = S[b.function_owner] and S[b.function_owner].env
  local fn = env and rawget(env, b.input_function)
  if type(fn) ~= "function" then return false, "no input function" end
  local prev = currentWho
  currentWho = env.__who
  local ok, res = E.protect(env.__who, fn, o, color or "White", value, false)
  currentWho = prev
  return ok, res
end

--- A player choosing a context-menu entry.
function E.menu(o, label, color)
  for _, m in ipairs(S[o].menu) do
    if m.label == label then
      local prev = currentWho
      currentWho = m.owner or currentWho
      local ok, res = E.protect(m.owner or { label = "menu", origin = "?" }, m.fn, color or "White", Vector(0, 0, 0), o)
      currentWho = prev
      return ok, res
    end
  end
  return false, "no menu item " .. tostring(label)
end

--- A player picking an object up and dropping it at pos.
function E.drop(o, pos, color, rot)
  color = color or "White"
  E.fire("onObjectPickUp", color, o)
  local st = S[o]
  local v = vecOf(pos)
  st.pos = { x = v.x, y = v.y, z = v.z }
  if rot then local r = vecOf(rot) st.rot = { x = r.x, y = r.y, z = r.z } end
  updateZones(o)
  E.fire("onObjectDrop", color, o)
  scheduleLanding(o, 6)
end

--- A player flipping an object (fires onObjectRotate like TTS).
function E.playerFlip(o, color)
  local st = S[o]
  local old = st.rot.z
  methods.flip(o)
  E.fire("onObjectRotate", o, st.rot.y, st.rot.z, color or "White", st.rot.y, old)
end

--- The player dropping an object into a container.
function E.playerPut(container, o)
  if not mayEnter(container, o) then return nil end
  return E.putInto(container, o)
end

function E.who(label, origin) currentWho = { label = label, origin = origin } end
function E.stateOfObj(o) return S[o] end
function E.getGlobalEnv() return globalEnv end
function E.byGuid(g) return byGuid[g] end

return E
