-- Entry point of the headless SCED harness (tests only).
--
--   lua5.2 tests/sced_real/run.lua --suite playthrough|runner
--       --table <assembled SCED table.lua> --src <SCED src folder>
--   lua5.2 tests/sced_real/run.lua --suite ... --fixture <fake table .json>
--   ... --snapshots <dir>   also write a table snapshot (JSON) after boot
--                           and after every step, for tools/godot_table
--
-- Boots the table in tests/sced_real/tts_emu.lua, then runs the suite. Each
-- check prints a line "@@CHECK <json>"; tests/sced_real/run.py (and the
-- pytest wrapper) read them. Exit code 0 when every check passed.

local here = (debug.getinfo(1, "S").source:match("^@(.*)[/\\]") or ".")
local ROOT = here .. "/../.."
local E = dofile(here .. "/tts_emu.lua")
local J = E.J

local args = {}
do
  local i = 1
  while i <= #arg do
    local a = arg[i]
    if a:sub(1, 2) == "--" then args[a:sub(3)] = arg[i + 1] ; i = i + 2 else i = i + 1 end
  end
end
local suite = args.suite or "playthrough"
E.echo = args.echo == "1"
E.quiet = args.verbose ~= "1"

local function readFile(p)
  local f = assert(io.open(p, "rb"))
  local s = f:read("*a")
  f:close()
  return s
end

------------------------------------------------------------------ checks --

local H = { E = E, ROOT = ROOT, passed = 0, failed = 0, checks = {}, mode = args.fixture and "fake" or "sced" }
H.readFile = readFile
H.payload = args.payload   -- a candidate Saved Object instead of dist/'s

local function emit(t)
  io.write("@@CHECK ", J.encode(t), "\n")
  io.flush()
end

function H.check(name, ok, detail)
  ok = ok and true or false
  if ok then H.passed = H.passed + 1 else H.failed = H.failed + 1 end
  local rec = { name = name, ok = ok, detail = detail ~= nil and tostring(detail) or nil, t = E.now }
  H.checks[#H.checks + 1] = rec
  emit(rec)
  io.write(string.format("%s %s%s\n", ok and "[PASS]" or "[FAIL]", name,
    detail ~= nil and ("  -- " .. tostring(detail)) or ""))
end

-- table snapshots for the Godot renderer (tools/godot_table): after boot and
-- after every step; a suite may also call H.snapshot(label) at any moment
H.snapDir = args.snapshots
H.snapCount = 0
local SNAP
function H.snapshot(label)
  if not H.snapDir then return nil end
  SNAP = SNAP or dofile(here .. "/snapshot.lua")
  local n = H.snapCount
  H.snapCount = n + 1
  local path = string.format("%s/%03d.json", H.snapDir, n)
  local ok, err = pcall(SNAP.write, E, path, { index = n, label = label, suite = suite, t = E.now })
  if not ok then io.write("[INFO] snapshot failed: " .. tostring(err) .. "\n") return nil end
  io.write("@@SNAPSHOT ", J.encode({ index = n, label = label, file = path }), "\n")
  return path
end

function H.info(msg) io.write("[INFO] " .. msg .. "\n") emit({ info = msg }) end

-- Lua errors raised since mark (optionally only from some origins)
function H.errorsSince(mark, filter)
  local out = {}
  for i = mark + 1, #E.errors do
    local e = E.errors[i]
    if not filter or filter(e) then out[#out + 1] = e end
  end
  return out
end

function H.describeErrors(list, n)
  local parts = {}
  for i = 1, math.min(#list, n or 3) do
    parts[#parts + 1] = string.format("%s: %s", list[i].where, list[i].msg)
  end
  if #list > (n or 3) then parts[#parts + 1] = string.format("(+%d more)", #list - (n or 3)) end
  return table.concat(parts, " || ")
end

--- A step: runs fn, then fails the step if any Lua error happened meanwhile.
function H.step(name, fn)
  H.info("== " .. name)
  local mark = #E.errors
  local ok, err = xpcall(fn, function(e) return debug.traceback(tostring(e), 2) end)
  if not ok then H.check(name .. ": harness step completed", false, err) end
  local errs = H.errorsSince(mark)
  H.check(name .. ": no Lua errors (campaign or SCED)", #errs == 0, #errs > 0 and H.describeErrors(errs) or nil)
  for _, e in ipairs(errs) do io.write("  [lua error] " .. tostring(e.trace) .. "\n") end
  H.snapshot(name)
end

------------------------------------------------------------------ table --

-- SCED's boards, sized from its own coordinates (see tts_emu.lua SIZE)
local SCED_SIZES = {
  ["9f334f"] = { 5.37, 0.1, 1.97 },      -- Mythos Area (MythosArea.ttslua MYTHOS_AREA_DATA)
  ["721ba2"] = { 3.6, 0.1, 3.6 },        -- Play Area (its 9x9 snap grid + margin)
  -- playmats: TTS sizes a Custom_Tile from its image (short side 2, the other
  -- by aspect); the playmat image is 4406x2098, and its snap points sit on the
  -- printed card slots at that size (checked in tools/godot_table renders)
  ["8b081b"] = { 4.2, 0.1, 2.0 }, ["bd0ff4"] = { 4.2, 0.1, 2.0 },
  ["383d8b"] = { 4.2, 0.1, 2.0 }, ["0840d5"] = { 4.2, 0.1, 2.0 },
  -- table surface (a Custom_Model at y -9 whose mesh top is 10.48 above its
  -- origin): a box reaching up to the real surface (y 1.48), so things
  -- dropped on the table rest on it, not 10 units below
  ["4ee1f2"] = { 200, 20.96, 200 },
}

local save
if args.fixture then
  save = J.decode(readFile(args.fixture))
  E.srcDirs = {}
else
  assert(args.table, "--table or --fixture is required")
  save = dofile(args.table)
  E.srcDirs = { args.src }
  for g, s in pairs(SCED_SIZES) do E.sizeOverride[g] = s end
  H.info("SCED table: " .. tostring(save.SaveName) .. " (commit " .. tostring(save.commit) .. ")")
end
for g, s in pairs(save.SizeOverride or {}) do E.sizeOverride[g] = s end

E.phase = "boot"
local t0 = os.clock()
local created = E.loadSave(save, "sced")
E.run(5)
H.info(string.format("table booted: %d objects, %d scripted, %.1fs cpu", #created,
  (function() local n = 0 for _, o in ipairs(created) do if E.S[o].env then n = n + 1 end end return n end)(),
  os.clock() - t0))
local bootErrors = {}
for _, e in ipairs(E.errors) do bootErrors[#bootErrors + 1] = e end
-- errors while the bare table boots come from the emulator's coverage of
-- SCED, not from the campaign (it is not on the table yet): reported, and a
-- failure only with --strict-boot 1
if #bootErrors > 0 then
  H.info(string.format("%d Lua error(s) while the bare table booted (emulator gaps): %s", #bootErrors,
    H.describeErrors(bootErrors, 6)))
end
if args["strict-boot"] == "1" or #bootErrors == 0 then
  H.check("table boots without Lua errors (emulator coverage of SCED)", #bootErrors == 0,
    #bootErrors > 0 and H.describeErrors(bootErrors, 6) or nil)
end
for _, e in ipairs(bootErrors) do io.write("  [boot error] " .. tostring(e.trace) .. "\n") end
H.bootErrorCount = #bootErrors
H.snapshot("the bare table after boot")
H.scedGuids = {}
for _, o in ipairs(created) do H.scedGuids[o.getGUID()] = true end
E.phase = "campaign"

------------------------------------------------------------------ suite --

local okSuite, errSuite = xpcall(function()
  dofile(here .. "/" .. suite .. ".lua")(H)
end, function(e) return debug.traceback(tostring(e), 2) end)
if not okSuite then H.check("suite '" .. suite .. "' ran to the end", false, errSuite) end

------------------------------------------------------------------ report --

local gaps = {}
for k, n in pairs(E.gaps) do gaps[#gaps + 1] = string.format("%s x%d", k, n) end
table.sort(gaps)
if #gaps > 0 then H.info("emulator gaps (unknown object members read): " .. table.concat(gaps, ", ")) end
if (E.destroyedAccess or 0) > 0 then
  H.info(string.format("%d access(es) to destroyed objects (warnings; TTS would error unless guarded by ~= nil)",
    E.destroyedAccess))
end
for _, w in ipairs(E.warnings) do
  if w:find("destroyed object", 1, true) then io.write("  [warn] " .. w:sub(1, 600) .. "\n") end
end
io.write(string.format("RESULT: %d passed, %d failed (suite %s, %s, %s, virtual %.1fs)\n", H.passed, H.failed,
  suite, H.mode, _VERSION, E.now))
emit({ done = true, passed = H.passed, failed = H.failed })
os.exit(H.failed == 0 and 0 or 1)
