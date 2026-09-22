-- Object scripts for the SCED fixture (tests only). sced_fixture.py splits this
-- file on the "--@@ <name>" markers and attaches each part to one object.

--@@ GUIDReferenceHandler
-- argonui/SCED src/core/GUIDReferenceHandler.ttslua, reduced to the lookups
-- GUIDReferenceApi exposes. The map is owner -> type -> guid.
local INDEX = {
  Mythos = { PlayArea = "5ce0a1", TokenSpawnTracker = "e3fa31", InvestigatorCounter = "f182ee" },
  White = { Playermat = "8b081b", InvestigatorSkillTracker = "e598c2" },
}

function getObjectByOwnerAndType(params)
  local owner = INDEX[params.owner]
  local guid = owner and owner[params.type]
  return guid and getObjectFromGUID(guid) or nil
end

function getObjectsByType(t)
  local out = {}
  for owner, types in pairs(INDEX) do
    if types[t] then out[owner] = getObjectFromGUID(types[t]) end
  end
  return out
end

function getObjectsByOwner(owner)
  local out = {}
  for t, guid in pairs(INDEX[owner] or {}) do out[t] = getObjectFromGUID(guid) end
  return out
end

--@@ PlayArea
-- src/playarea/PlayArea.ttslua isInPlayArea: centre point inside the play
-- area's bounds (a fixed rectangle here).
function isInPlayArea(object)
  local p = object.getPosition()
  return p.x > -45 and p.x < -15 and p.z > -15 and p.z < 20
end

--@@ TokenSpawnTracker
-- src/tokens/TokenSpawnTracker.ttslua (same state and functions).
local spawnedCardGuids = {}

local function convertToGuid(objOrGuid)
  if type(objOrGuid) == "string" then return objOrGuid end
  return objOrGuid.getGUID()
end

function hasSpawnedTokens(objOrGuid) return spawnedCardGuids[convertToGuid(objOrGuid)] == true end
function markTokensSpawned(objOrGuid) spawnedCardGuids[convertToGuid(objOrGuid)] = true end
function resetTokensSpawned(objOrGuid) spawnedCardGuids[convertToGuid(objOrGuid)] = nil end
function resetAll() spawnedCardGuids = {} end

--@@ InvestigatorCounter
-- src/playarea/ActiveInvestigatorCounter.ttslua: the value lives in `val`.
val = 3
function updateVal(v) val = v end

--@@ Playermat
-- src/playermat/Playermat.ttslua: activeInvestigatorData is filled when an
-- investigator card lands on the mat (maybeUpdateActiveInvestigator). The
-- fixture starts with a Still Hour investigator seated on White.
matColor = "White"
playerColor = "White"
local activeInvestigatorData = { id = "sthrelias", class = "Guardian", miniId = "sthr--m" }
function getActiveInvestigatorData() return activeInvestigatorData end
function setActiveInvestigatorData(newData) activeInvestigatorData = newData end

--@@ InvestigatorSkillTracker
-- src/playermat/InvestigatorSkillTracker.ttslua (same state, labels, save).
stats = { 1, 1, 1, 1 }
function updateSave() self.script_state = JSON.encode(stats) end
function onLoad(savedData)
  if savedData and savedData ~= "" then stats = JSON.decode(savedData) or { 1, 1, 1, 1 } end
  for index = 1, 4 do
    self.createButton({ click_function = "noop", function_owner = self, label = stats[index] .. "   " })
  end
end
function updateButtonLabel(index)
  self.editButton({ index = index - 1, label = stats[index] .. "   " })
end
function updateStats(newStats)
  if newStats and #newStats == 4 then
    stats = newStats
    for i = 1, 4 do updateButtonLabel(i) end
    updateSave()
  end
end
