-- Fake Tabletop Simulator scripting environment (tests only).
--
-- Executes one "Execute Lua Code" chunk the way TTS would in Global, with the
-- slice of the TTS API the relay runner and the Still Hour control token use:
-- spawnObjectJSON, object scripts with onLoad/onSave/buttons/call/reload,
-- bags + takeObject, tags, Wait.time/frames/condition on a virtual clock,
-- Player.lookAt, sendExternalMessage.
--
-- Every message TTS would send to the external editor is written to stdout as
--   @@MSG <json>
-- and tests/tts_fake/fake_tts.py forwards it to the relay.
--
-- Usage: lua5.2 tests/tts_fake/mock_tts.lua <chunk.lua> [preexisting.json]

local dir = arg[0]:match("^(.*)[/\\]") or "."
package.path = dir .. "/?.lua;" .. package.path
local J = require("json")

local function emit(msg) io.write("@@MSG ", J.encode(msg), "\n") ; io.flush() end

------------------------------------------------------------------ clock --
local now, queue, seq = 0, {}, 0
local function schedule(t, fn)
  seq = seq + 1
  queue[#queue + 1] = { t = t, seq = seq, fn = fn }
end

local function report(err, guid)
  emit({ messageID = 3, error = tostring(err), guid = guid or "-1",
         errorMessagePrefix = "Error in Script: " })
end

local Wait = {}
function Wait.time(fn, s) schedule(now + (s or 0), fn) ; return seq end
function Wait.frames(fn, n) schedule(now + (n or 1) / 60, fn) ; return seq end
function Wait.condition(fn, cond, timeout, timeoutFn)
  local start = now
  local function poll()
    local ok, v = pcall(cond)
    if not ok then report(v) ; return end
    if v then fn() return end
    if timeout and now - start >= timeout then
      if timeoutFn then timeoutFn() end
      return
    end
    schedule(now + 1 / 60, poll)
  end
  schedule(now, poll)
  return seq
end
function Wait.stop() end

------------------------------------------------------------------ objects --
local objects, guidSeq = {}, 0
local G  -- Global env, filled below

local function deepcopy(v)
  if type(v) ~= "table" then return v end
  local t = {}
  for k, x in pairs(v) do t[k] = deepcopy(x) end
  return t
end

local TYPE = { Bag = "Bag", Custom_Model_Bag = "Bag", Deck = "Deck", DeckCustom = "Deck",
               Card = "Card", CardCustom = "Card" }

local makeObject

local function method(o, fn)
  -- TTS object methods work as o.f(x) and o:f(x); strip a leading self
  return function(a, ...)
    if a == o then return fn(...) end
    return fn(a, ...)
  end
end

function makeObject(data)
  guidSeq = guidSeq + 1
  local o = {}
  local st = { data = data, buttons = {}, tags = {}, env = nil, destroyed = false,
               guid = string.format("%06x", 0xa00000 + guidSeq) }
  for _, t in ipairs(data.Tags or {}) do st.tags[t] = true end
  local t = data.Transform or {}
  st.pos = { x = t.posX or 0, y = t.posY or 1, z = t.posZ or 0 }
  local contained = deepcopy(data.ContainedObjects or {})
  data.ContainedObjects = nil

  local fields = {
    type = TYPE[data.Name] or "Generic",
    guid = st.guid,
    spawning = false,
  }
  local function state()
    if st.env and st.env.onSave then
      local ok, v = pcall(st.env.onSave)
      if ok then return v or "" end
      report(v, st.guid)
    end
    return data.LuaScriptState or ""
  end
  setmetatable(o, {
    __index = function(_, k)
      if k == "script_state" then return state() end
      return fields[k]
    end,
  })
  o.getName = method(o, function() return data.Nickname or "" end)
  o.getGMNotes = method(o, function() return data.GMNotes or "" end)
  o.getLuaScript = method(o, function() return data.LuaScript or "" end)
  o.getPosition = method(o, function() return { x = st.pos.x, y = st.pos.y, z = st.pos.z } end)
  o.getButtons = method(o, function()
    if #st.buttons == 0 then return nil end
    return deepcopy(st.buttons)
  end)
  o.createButton = method(o, function(def) st.buttons[#st.buttons + 1] = deepcopy(def) ; return true end)
  o.clearButtons = method(o, function() st.buttons = {} ; return true end)
  o.addTag = method(o, function(tag) st.tags[tag] = true ; return true end)
  o.hasTag = method(o, function(tag) return st.tags[tag] == true end)
  o.getTags = method(o, function()
    local l = {} for k in pairs(st.tags) do l[#l + 1] = k end return l
  end)
  o.getObjects = method(o, function()
    local l = {}
    for i, c in ipairs(contained) do
      l[i] = { index = i - 1, name = c.Nickname or "", guid = c.GUID or "", gm_notes = c.GMNotes or "" }
    end
    return l
  end)
  o.getData = method(o, function()
    local d = deepcopy(data)
    d.ContainedObjects = deepcopy(contained)
    d.LuaScriptState = state()
    d.Tags = o.getTags()
    return d
  end)
  o.call = method(o, function(name, param)
    local fn = st.env and st.env[name]
    if type(fn) ~= "function" then error("call: no function " .. tostring(name)) end
    return fn(param)
  end)
  o.takeObject = method(o, function(p)
    p = p or {}
    local idx = (p.index or 0) + 1
    local c = table.remove(contained, idx)
    if not c then return nil end
    local pos = p.position
    if pos then
      c.Transform = c.Transform or {}
      c.Transform.posX, c.Transform.posY, c.Transform.posZ = pos[1] or pos.x, pos[2] or pos.y, pos[3] or pos.z
    end
    local child = makeObject(c)
    if p.callback_function then Wait.frames(function() p.callback_function(child) end, 2) end
    return child
  end)
  o.destruct = method(o, function()
    st.destroyed = true
    for i, x in ipairs(objects) do if x == o then table.remove(objects, i) break end end
    return true
  end)
  o.reload = method(o, function()
    local d = o.getData()
    o.destruct()
    return makeObject(d)
  end)

  objects[#objects + 1] = o
  if data.LuaScript and data.LuaScript ~= "" then
    local env = setmetatable({ self = o }, { __index = G })
    st.env = env
    local chunk, err = load(data.LuaScript, "=" .. st.guid, "t", env)
    if not chunk then report(err, st.guid) else
      local ok, e = pcall(chunk)
      if not ok then report(e, st.guid)
      elseif env.onLoad then
        local ok2, e2 = pcall(env.onLoad, data.LuaScriptState or "")
        if not ok2 then report(e2, st.guid) end
      end
    end
  end
  return o
end

------------------------------------------------------------------ Global --
local host = { color = "White", host = true, seated = true, steam_name = "tester" }
host.lookAt = function(p) host.lastLook = p ; return true end

G = setmetatable({
  JSON = { encode = J.encode, decode = J.decode },
  Wait = Wait,
  print = function(...)
    local parts = {}
    for i = 1, select("#", ...) do parts[#parts + 1] = tostring((select(i, ...))) end
    emit({ messageID = 2, message = table.concat(parts, "\t") })
  end,
  broadcastToAll = function(msg) emit({ messageID = 2, message = "(broadcast) " .. tostring(msg) }) end,
  printToAll = function(msg) emit({ messageID = 2, message = tostring(msg) }) end,
  log = function() end,
  sendExternalMessage = function(t) emit({ messageID = 4, customMessage = t }) ; return true end,
  getObjects = function() local l = {} for i, o in ipairs(objects) do l[i] = o end return l end,
  getObjectsWithTag = function(tag)
    local l = {}
    for _, o in ipairs(objects) do if o.hasTag(tag) then l[#l + 1] = o end end
    return l
  end,
  destroyObject = function(o) return o.destruct() end,
  spawnObjectJSON = function(p)
    local data = J.decode(p.json)
    local o = makeObject(data)
    if p.callback_function then Wait.frames(function() p.callback_function(o) end, 3) end
    return o
  end,
  Player = {
    getPlayers = function() return { host } end,
    getSpectators = function() return {} end,
  },
}, { __index = _G })

------------------------------------------------------------------ run --
local path, pre = arg[1], arg[2]
if pre then
  local f = assert(io.open(pre, "rb")) ; local s = f:read("*a") ; f:close()
  for _, d in ipairs(J.decode(s)) do makeObject(d) end
end
local f = assert(io.open(path, "rb"))
local src = f:read("*a")
f:close()
local chunk, err = load(src, "=chunk_0", "t", G)
if not chunk then
  report(err)
else
  local ok, ret = pcall(chunk)
  if not ok then report(ret)
  elseif ret ~= nil then emit({ messageID = 5, returnValue = ret }) end
end

-- drain the virtual clock
local guard = 0
while #queue > 0 and guard < 200000 do
  guard = guard + 1
  table.sort(queue, function(a, b) if a.t == b.t then return a.seq < b.seq end return a.t < b.t end)
  local ev = table.remove(queue, 1)
  now = ev.t
  local ok, e = pcall(ev.fn)
  if not ok then report(e) end
end
io.stderr:write(string.format("mock_tts: virtual time %.2fs, %d objects\n", now, #objects))
