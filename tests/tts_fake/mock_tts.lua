-- Fake Tabletop Simulator scripting environment (tests only).
--
-- Executes one "Execute Lua Code" chunk the way TTS would in Global, with the
-- slice of the TTS API the relay runner, the Still Hour control token, the
-- board wiring, the campaign log and SCED's memory bag use:
-- spawnObjectJSON/spawnObjectData (GUIDs kept, like TTS), getObjectFromGUID,
-- object scripts with onLoad/onSave/script_state/buttons/inputs/context menu/
-- call/reload/getVar/setVar, States (setState), transforms + flip, bounds,
-- bags/decks with takeObject (index or guid)/putObject, tags, universal table
-- events (onObjectEnterContainer / onObjectLeaveContainer / onObjectDestroy /
-- onObjectSpawn), a `Global` object, Vector, Wait.time/frames/condition on a
-- virtual clock, Player.lookAt, sendExternalMessage. Signatures follow the
-- official API docs (Berserk-Games/Tabletop-Simulator-API).
--
-- A preexisting object named "__Global__" supplies the Global script: the SCED
-- fixture (tests/tts_fake/sced/) uses it to stand in for SCED's Global.
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
local byGuid = {}
local G  -- Global env, filled below
local globalEnv  -- the Global script's env (SCED fixture), if any

local function guidInUse(g)
  for _, x in ipairs(objects) do if x.guid == g then return true end end
  return false
end

local function Vector(x, y, z)
  if type(x) == "table" then x, y, z = x.x or x[1], x.y or x[2], x.z or x[3] end
  local v = { x = x or 0, y = y or 0, z = z or 0 }
  v[1], v[2], v[3] = v.x, v.y, v.z
  return setmetatable(v, {
    __add = function(a, b) return Vector(a.x + b.x, a.y + b.y, a.z + b.z) end,
    __index = { scale = function(a, b) return Vector(a.x * b.x, a.y * b.y, a.z * b.z) end },
  })
end

local function deepcopy(v)
  if type(v) ~= "table" then return v end
  local t = {}
  for k, x in pairs(v) do t[k] = deepcopy(x) end
  return t
end

local TYPE = { Bag = "Bag", Custom_Model_Bag = "Bag", Deck = "Deck", DeckCustom = "Deck",
               Card = "Card", CardCustom = "Card", Custom_Tile = "Tile" }

local makeObject

-- Universal event handlers run in every object script (and Global).
local function fire(name, ...)
  local envs = {}
  for _, o in ipairs(objects) do
    local env = o.__env
    if env and type(env[name]) == "function" then envs[#envs + 1] = { env, o.guid } end
  end
  if globalEnv and type(globalEnv[name]) == "function" then envs[#envs + 1] = { globalEnv, "-1" } end
  for _, e in ipairs(envs) do
    local ok, err = pcall(e[1][name], ...)
    if not ok then report(err, e[2]) end
  end
end

local function method(o, fn)
  -- TTS object methods work as o.f(x) and o:f(x); strip a leading self
  return function(a, ...)
    if a == o then return fn(...) end
    return fn(a, ...)
  end
end

local function vecOf(p)
  if p == nil then return nil end
  return { x = p.x or p[1] or 0, y = p.y or p[2] or 0, z = p.z or p[3] or 0 }
end

local function newGuid(want)
  if type(want) == "string" and #want > 0 and not byGuid[want] then return want end
  repeat
    guidSeq = guidSeq + 1
    want = string.format("%06x", 0xa00000 + guidSeq)
  until not byGuid[want]
  return want
end

function makeObject(data, stateId)
  local o = {}
  local st = { data = data, buttons = {}, inputs = {}, menu = {}, tags = {}, env = nil,
               destroyed = false, guid = newGuid(data.GUID), locked = data.Locked == true }
  data.GUID = st.guid
  for _, t in ipairs(data.Tags or {}) do st.tags[t] = true end
  local t = data.Transform or {}
  st.pos = { x = t.posX or 0, y = t.posY or 1, z = t.posZ or 0 }
  st.rot = { x = t.rotX or 0, y = t.rotY or 0, z = t.rotZ or 0 }
  st.scale = { x = t.scaleX or 1, y = t.scaleY or 1, z = t.scaleZ or 1 }
  local states = data.States
  data.States = nil
  st.stateId = states and (stateId or 1) or -1
  local contained = deepcopy(data.ContainedObjects or {})
  data.ContainedObjects = nil

  local fields = {
    type = TYPE[data.Name] or "Generic",
    guid = st.guid,
    spawning = false,
    resting = true,
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
      if k == "is_face_down" then
        local z = st.rot.z % 360
        return z > 90 and z < 270
      end
      if k == "__env" then return st.env end
      if k == "loading_custom" then return false end
      if k == "memo" then return data.Memo or "" end
      return fields[k]
    end,
    -- Object.memo (saved user-data) and Object.script_state are writable
    __newindex = function(t, k, v)
      if k == "memo" then data.Memo = v
      elseif k == "script_state" then data.LuaScriptState = v
      else rawset(t, k, v) end
    end,
  })
  local function tags()
    local l = {} for k in pairs(st.tags) do l[#l + 1] = k end table.sort(l) return l
  end
  o.getGUID = method(o, function() return st.guid end)
  o.getName = method(o, function() return data.Nickname or "" end)
  o.setName = method(o, function(n) data.Nickname = n ; return true end)
  o.getDescription = method(o, function() return data.Description or "" end)
  o.setDescription = method(o, function(s) data.Description = s ; return true end)
  o.getGMNotes = method(o, function() return data.GMNotes or "" end)
  o.getLuaScript = method(o, function() return data.LuaScript or "" end)
  o.getPosition = method(o, function() return Vector(st.pos) end)
  o.setPosition = method(o, function(p) st.pos = Vector(p) ; return true end)
  o.setPositionSmooth = o.setPosition
  o.getRotation = method(o, function() return Vector(st.rot) end)
  o.setRotation = method(o, function(r) st.rot = Vector(r) ; return true end)
  o.getScale = method(o, function() return Vector(st.scale) end)
  o.getLock = method(o, function() return st.locked end)
  o.setLock = method(o, function(v) st.locked = v and true or false ; return true end)
  o.highlightOn = method(o, function() return true end)
  o.highlightOff = method(o, function() return true end)
  -- a 2 x 2.6 local footprint (a page-shaped token) scaled like TTS does
  o.getBoundsNormalized = method(o, function()
    return { center = Vector(st.pos), offset = Vector(0, 0.1 * st.scale.y, 0),
             size = Vector(2 * st.scale.x, 0.2 * st.scale.y, 2.6 * st.scale.z) }
  end)
  o.getBounds = o.getBoundsNormalized
  o.getGUID = method(o, function() return st.guid end)
  o.getInputs = method(o, function()
    if #st.inputs == 0 then return nil end
    return deepcopy(st.inputs)
  end)
  o.createInput = method(o, function(def) st.inputs[#st.inputs + 1] = deepcopy(def) ; return true end)
  o.clearInputs = method(o, function() st.inputs = {} ; return true end)
  o.editInput = method(o, function(p)
    local b = st.inputs[(p.index or 0) + 1]
    if not b then error("editInput: no input " .. tostring(p.index)) end
    for k, v in pairs(p) do if k ~= "index" then b[k] = v end end
    return true
  end)
  o.editButton = method(o, function(p)
    local b = st.buttons[(p.index or 0) + 1]
    if not b then error("editButton: no button " .. tostring(p.index)) end
    for k, v in pairs(p) do if k ~= "index" then b[k] = v end end
    return true
  end)
  o.addContextMenuItem = method(o, function(label, fn) st.menu[#st.menu + 1] = { label, fn } ; return true end)
  o.setVar = method(o, function(k, v) if st.env then st.env[k] = v end ; return true end)
  o.getVar = method(o, function(k) return st.env and st.env[k] end)
  o.getStateId = method(o, function() return st.stateId end)
  o.getStates = method(o, function()
    local l = {}
    for id, d in pairs(states or {}) do
      l[#l + 1] = { id = tonumber(id), name = d.Nickname or "", guid = d.GUID or "" }
    end
    return l
  end)
  o.setState = method(o, function(id)
    if not states or not states[tostring(id)] then error("setState: no state " .. tostring(id)) end
    local cur = o.getData()
    cur.States = nil
    local nxt = deepcopy(states[tostring(id)])
    nxt.States = {}
    for k, d in pairs(states) do if k ~= tostring(id) then nxt.States[k] = deepcopy(d) end end
    nxt.States[tostring(st.stateId)] = cur
    nxt.Transform = cur.Transform
    o.destruct()
    return makeObject(nxt, id)
  end)
  o.flip = method(o, function() st.rot = Vector(st.rot.x, st.rot.y, (st.rot.z + 180) % 360) ; return true end)
  o.isDestroyed = method(o, function() return st.destroyed end)
  o.getButtons = method(o, function()
    if #st.buttons == 0 then return nil end
    local l = deepcopy(st.buttons)
    for i, b in ipairs(l) do b.index = i - 1 end
    return l
  end)
  o.createButton = method(o, function(def) st.buttons[#st.buttons + 1] = deepcopy(def) ; return true end)
  o.editButton = method(o, function(p)
    local b = st.buttons[(p.index or 0) + 1]
    if not b then return false end
    for k, v in pairs(p) do if k ~= "index" then b[k] = v end end
    return true
  end)
  o.getMemo = method(o, function() return data.Memo or "" end)
  o.setMemo = method(o, function(v) data.Memo = v ; return true end)
  o.removeButton = method(o, function(i) table.remove(st.buttons, (i or 0) + 1) ; return true end)
  o.clearButtons = method(o, function() st.buttons = {} ; return true end)
  o.addTag = method(o, function(tag) st.tags[tag] = true ; return true end)
  o.removeTag = method(o, function(tag) st.tags[tag] = nil ; return true end)
  o.hasTag = method(o, function(tag) return st.tags[tag] == true end)
  o.getTags = method(o, tags)
  o.getVar = method(o, function(name) return st.env and st.env[name] end)
  o.setVar = method(o, function(name, v) if st.env then st.env[name] = v end ; return true end)
  o.getObjects = method(o, function()
    local l = {}
    for i, c in ipairs(contained) do
      l[i] = { index = i - 1, name = c.Nickname or "", nickname = c.Nickname or "", guid = c.GUID or "",
               gm_notes = c.GMNotes or "", description = c.Description or "", memo = c.Memo or "",
               tags = deepcopy(c.Tags or {}), lua_script_state = c.LuaScriptState or "" }
    end
    return l
  end)
  o.getQuantity = method(o, function() return #contained end)
  o.getData = method(o, function()
    local d = deepcopy(data)
    d.ContainedObjects = deepcopy(contained)
    d.LuaScriptState = state()
    d.Tags = o.getTags()
    d.Locked = st.locked
    d.Transform = { posX = st.pos.x, posY = st.pos.y, posZ = st.pos.z,
                    rotX = st.rot.x, rotY = st.rot.y, rotZ = st.rot.z,
                    scaleX = st.scale.x, scaleY = st.scale.y, scaleZ = st.scale.z }
    if states then d.States = deepcopy(states) end
    return d
  end)
  o.call = method(o, function(name, param)
    local fn = st.env and st.env[name]
    if type(fn) ~= "function" then error("call: no function " .. tostring(name)) end
    return fn(param)
  end)

  local function forget()
    st.destroyed = true
    byGuid[st.guid] = nil
    for i, x in ipairs(objects) do if x == o then table.remove(objects, i) break end end
  end

  o.takeObject = method(o, function(p)
    p = p or {}
    local idx = (p.index or 0) + 1
    if p.guid then
      idx = nil
      for i, c in ipairs(contained) do if c.GUID == p.guid then idx = i end end
      if not idx then return nil end
    end
    local c = table.remove(contained, idx)
    if not c then return nil end
    c.Transform = c.Transform or {}
    local pos = vecOf(p.position) or { x = st.pos.x, y = st.pos.y + 2, z = st.pos.z }
    c.Transform.posX, c.Transform.posY, c.Transform.posZ = pos.x, pos.y, pos.z
    local rot = vecOf(p.rotation)
    if rot then c.Transform.rotX, c.Transform.rotY, c.Transform.rotZ = rot.x, rot.y, rot.z end
    local child = makeObject(c)
    fire("onObjectLeaveContainer", o, child)
    if p.callback_function then Wait.frames(function() p.callback_function(child) end, 2) end
    return child
  end)
  o.putObject = method(o, function(other)
    local d = other.getData()
    other.__forget()
    contained[#contained + 1] = d
    fire("onObjectEnterContainer", o, other)
    return o
  end)
  o.__forget = forget
  o.destruct = method(o, function()
    if st.destroyed then return true end
    fire("onObjectDestroy", o)
    forget()
    return true
  end)
  o.reload = method(o, function()
    local d = o.getData()
    o.destruct()
    return makeObject(d, st.stateId > 0 and st.stateId or nil)
  end)

  byGuid[st.guid] = o
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
  fire("onObjectSpawn", o)
  return o
end

------------------------------------------------------------------ Global --
local host = { color = "White", host = true, seated = true, steam_name = "tester" }
host.lookAt = function(p) host.lastLook = p ; return true end

-- `Global` as scripts see it: getVar/setVar/getTable/call into the Global script.
local GlobalObj = {}
GlobalObj.getVar = function(name) return globalEnv and globalEnv[name] or nil end
GlobalObj.setVar = function(name, v) if globalEnv then globalEnv[name] = v end ; return true end
GlobalObj.getTable = function(name) return globalEnv and globalEnv[name] or nil end
GlobalObj.call = function(name, param)
  local fn = globalEnv and globalEnv[name]
  if type(fn) ~= "function" then error("Global.call: no function " .. tostring(name)) end
  return fn(param)
end

local function spawnData(data, p)
  p = p or {}
  data = deepcopy(data)
  data.Transform = data.Transform or {}
  local pos, rot = vecOf(p.position), vecOf(p.rotation)
  if pos then data.Transform.posX, data.Transform.posY, data.Transform.posZ = pos.x, pos.y, pos.z end
  if rot then data.Transform.rotX, data.Transform.rotY, data.Transform.rotZ = rot.x, rot.y, rot.z end
  local o = makeObject(data)
  if p.callback_function then Wait.frames(function() p.callback_function(o) end, 3) end
  return o
end

G = setmetatable({
  JSON = { encode = J.encode, decode = J.decode },
  Wait = Wait,
  Global = GlobalObj,
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
  getObjectFromGUID = function(g) return byGuid[g] end,
  Vector = Vector,
  getObjectsWithTag = function(tag)
    local l = {}
    for _, o in ipairs(objects) do if o.hasTag(tag) then l[#l + 1] = o end end
    return l
  end,
  destroyObject = function(o) return o.destruct() end,
  spawnObjectJSON = function(p)
    return spawnData(J.decode(p.json), p)
  end,
  spawnObjectData = function(p) return spawnData(p.data, p) end,
  Player = {
    getPlayers = function() return { host } end,
    getSpectators = function() return {} end,
  },
}, { __index = _G })

------------------------------------------------------------------ run --
local path, pre = arg[1], arg[2]
if pre then
  local f = assert(io.open(pre, "rb")) ; local s = f:read("*a") ; f:close()
  for _, d in ipairs(J.decode(s)) do
    if d.Name == "__Global__" then
      globalEnv = setmetatable({ self = GlobalObj }, { __index = G })
      local chunk, err = load(d.LuaScript or "", "=Global", "t", globalEnv)
      if not chunk then report(err) else
        local ok, e = pcall(chunk)
        if not ok then report(e) end
      end
    else
      makeObject(d)
    end
  end
  if globalEnv and globalEnv.onLoad then
    local ok, e = pcall(globalEnv.onLoad, "")
    if not ok then report(e) end
  end
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
while #queue > 0 and guard < 400000 do
  guard = guard + 1
  table.sort(queue, function(a, b) if a.t == b.t then return a.seq < b.seq end return a.t < b.t end)
  local ev = table.remove(queue, 1)
  now = ev.t
  local ok, e = pcall(ev.fn)
  if not ok then report(e) end
end
io.stderr:write(string.format("mock_tts: virtual time %.2fs, %d objects\n", now, #objects))
