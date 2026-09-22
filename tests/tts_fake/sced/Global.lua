-- Stand-in for SCED's Global script (tests only).
--
-- Reproduces, with the same names, parameters and return shapes, the Global
-- functions SCED's public API wrappers call (argonui/SCED:
-- src/chaosbag/ChaosBagApi.ttslua -> src/Global/Global.ttslua,
-- src/tokens/TokenManagerApi.ttslua -> Global callTable/TokenManager), plus
-- MOD_VERSION / ID_URL_MAP from src/core/Constants.ttslua. Bodies follow the
-- real ones; only physics is replaced (a token spawned "into" the bag is put
-- there with putObject, which the real game does by dropping it in).

MOD_VERSION = "4.9.2"

ID_URL_MAP = {
  ['blue']    = { name = "Elder Sign", url = "https://example.invalid/elder.png" },
  ['p1']      = { name = "+1", url = "https://example.invalid/p1.png" },
  ['0']       = { name = "0", url = "https://example.invalid/0.png" },
  ['m1']      = { name = "-1", url = "https://example.invalid/m1.png" },
  ['m2']      = { name = "-2", url = "https://example.invalid/m2.png" },
  ['m3']      = { name = "-3", url = "https://example.invalid/m3.png" },
  ['skull']   = { name = "Skull", url = "https://example.invalid/skull.png" },
  ['cultist'] = { name = "Cultist", url = "https://example.invalid/cultist.png" },
  ['tablet']  = { name = "Tablet", url = "https://example.invalid/tablet.png" },
  ['elder']   = { name = "Elder Thing", url = "https://example.invalid/elderthing.png" },
  ['red']     = { name = "Auto-fail", url = "https://example.invalid/red.png" },
  ['bless']   = { name = "Bless", url = "https://example.invalid/bless.png" },
  ['curse']   = { name = "Curse", url = "https://example.invalid/curse.png" },
}

local chaosTokens = {}
local bagSearchers = {}
local namesToIds = {}
for k, v in pairs(ID_URL_MAP) do namesToIds[v.name] = k end

local function handler() return getObjectFromGUID("123456") end
local function byOwnerAndType(owner, t)
  return handler().call("getObjectByOwnerAndType", { owner = owner, type = t })
end

function onObjectSearchStart(object, playerColor)
  if object.getName() == "Chaos Bag" then bagSearchers[playerColor] = true end
end

function onObjectSearchEnd(object, playerColor)
  if object.getName() == "Chaos Bag" then bagSearchers[playerColor] = nil end
end

-- test hook: pretend someone is (not) searching the bag
function setBagSearched(flag) bagSearchers.Test = flag or nil end

function findChaosBag()
  for _, obj in ipairs(getObjects()) do
    if obj.getName() == "Chaos Bag" or obj.getDescription() == "Chaos Bag" then
      return obj
    end
  end
  printToAll("Chaos bag couldn't be found.", "Red")
end

function canTouchChaosTokens()
  for _, searching in pairs(bagSearchers) do
    if searching then
      broadcastToAll("Someone is searching the chaos bag, can't touch the tokens.", "Red")
      return false
    end
  end
  return true
end

function getChaosTokensinPlay()
  return chaosTokens
end

function getChaosBagState()
  local tokens = {}
  local chaosBag = findChaosBag()
  for _, v in ipairs(chaosBag.getObjects()) do
    local id = namesToIds[v.name]
    if id then
      table.insert(tokens, id)
    else
      printToAll(v.name .. " token not recognized. Will not be recorded.", "Yellow")
    end
  end
  return tokens
end

function spawnChaosToken(id)
  if not canTouchChaosTokens() then return end
  local chaosBag = findChaosBag()
  if not chaosBag then return end
  id = id:lower()
  local idData = ID_URL_MAP[id]
  if idData then
    local p = chaosBag.getPosition()
    chaosBag.setLock(true)
    return spawnObjectData({
      data = {
        Name = "Custom_Tile", Nickname = idData.name, Hands = false, HideWhenFaceDown = false,
        ColorDiffuse = { r = 1, g = 1, b = 1 },
        CustomImage = { CustomTile = { Stretch = true, Thickness = 0.1, Type = 2 }, ImageURL = idData.url },
        Transform = { posX = p.x, posY = p.y + 0.4, posZ = p.z, rotX = 0, rotY = 0, rotZ = 0,
                      scaleX = 0.81, scaleY = 1, scaleZ = 0.81 },
      },
      callback_function = function(o)
        chaosBag.setLock(false)
        chaosBag.putObject(o)       -- physics stand-in
      end,
    })
  end
end

function removeChaosToken(id)
  if not canTouchChaosTokens() then return end
  local tokens = {}
  local chaosBag = findChaosBag()
  local name = ID_URL_MAP[id].name
  for _, v in ipairs(chaosBag.getObjects()) do
    if v.name == name then table.insert(tokens, v.guid) end
  end
  if #tokens == 0 then
    printToAll("No " .. name .. " tokens in the chaos bag.", "Yellow")
    return
  end
  chaosBag.takeObject({
    guid = tokens[1], smooth = false,
    callback_function = function(obj) obj.destruct() end,
  })
end

-- simplified draw: same parameter table, same token selection by nickname
function drawChaosToken(params)
  if not canTouchChaosTokens() then return end
  local chaosBag = findChaosBag()
  if #chaosBag.getObjects() == 0 then return end
  local takeParameters = params.takeParameters or {}
  if params.tokenType then
    for i, t in ipairs(chaosBag.getObjects()) do
      if t.nickname == params.tokenType then takeParameters.index = i - 1 end
    end
  end
  local token = chaosBag.takeObject(takeParameters)
  table.insert(chaosTokens, token)
  return token
end

function returnChaosTokens()
  local chaosBag = findChaosBag()
  for _, token in ipairs(chaosTokens) do
    if token ~= nil and not token.isDestroyed() then chaosBag.putObject(token) end
  end
  chaosTokens = {}
end

------------------------------------------------------------ TokenManager --

TokenManager = {}

function TokenManager.getUses(card)
  local metadata = JSON.decode(card.getGMNotes()) or {}
  if metadata.type == "Location" then
    if card.is_face_down and metadata.locationBack ~= nil then
      return metadata.locationBack.uses
    elseif not card.is_face_down and metadata.locationFront ~= nil then
      return metadata.locationFront.uses
    end
  elseif not card.is_face_down then
    return metadata.uses
  end
  return nil
end

function TokenManager.spawnForCard(params)
  local tracker = byOwnerAndType("Mythos", "TokenSpawnTracker")
  if tracker.call("hasSpawnedTokens", params.card.getGUID()) then return end
  local uses = TokenManager.getUses(params.card)
  if uses == nil then return end
  local investigators = byOwnerAndType("Mythos", "InvestigatorCounter").getVar("val")
  local p = params.card.getPosition()
  for _, useInfo in ipairs(uses) do
    local n = (useInfo.count or 0) + (useInfo.countPerInvestigator or 0) * investigators
    for i = 1, n do
      spawnObjectData({ data = { Name = "Custom_Token", Nickname = useInfo.type or "Clue",
        Tags = { "SCEDMockToken" },
        Transform = { posX = p.x + 0.3 * i, posY = p.y + 0.5, posZ = p.z } } })
    end
  end
  tracker.call("markTokensSpawned", params.card.getGUID())
end

-- SCED's generic dispatcher (Global.ttslua callTable), used by TokenManagerApi.
function callTable(params)
  local keys = params[1] or {}
  local arg = params[2] or nil
  local var = _ENV   -- the Global script env (SCED: _G)
  for _, key in ipairs(keys) do
    var = var[key]
    if type(var) ~= "table" then break end
  end
  if type(var) ~= "function" then return end
  return var(arg)
end
