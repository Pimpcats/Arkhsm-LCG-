-- Object scripts for the SCED fixture (tests only). sced_fixture.py splits this
-- file on the "--@@ <name>" markers and attaches each part to one object.

--@@ GUIDReferenceHandler
-- argonui/SCED src/core/GUIDReferenceHandler.ttslua, reduced to the lookups
-- GUIDReferenceApi exposes. The map is owner -> type -> guid.
local INDEX = {
  Mythos = { PlayArea = "5ce0a1", TokenSpawnTracker = "e3fa31", InvestigatorCounter = "f182ee" },
  White = { Playermat = "8b081b" },
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
matColor = "White"
playerColor = "White"
