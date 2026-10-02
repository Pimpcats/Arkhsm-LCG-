-- Runs the relay's in-game suite (tools/tts_relay/ingame_runner.lua) on the
-- emulated table, exactly as the relay sends it into the owner's TTS: the
-- job's payloads are prepended as a RELAY table and the chunk executes in
-- Global's script context ("Execute Lua Code", guid -1). One suite, two
-- environments. Each result the runner reports becomes a check here.

return function(H)
  local E, J = H.E, H.E.J
  local job = J.decode(H.readFile(H.ROOT .. "/tools/tts_relay/job.json"))
  local parts = { "local RELAY = { run = \"emulator\", pause = 0, payloads = {" }
  for _, p in ipairs(job.payloads) do
    local text = H.readFile(H.ROOT .. "/" .. p.file)
    local d = J.decode(text)
    -- a TTS save (ObjectStates) spawns each object; a single object spawns itself
    local list = d.ObjectStates or { d }
    for i, o in ipairs(list) do
      local name = p.file:match("([^/]+)%.json$") .. (#list > 1 and ("#" .. i) or "")
      parts[#parts + 1] = string.format("{ name = %q, json = %q%s },", name, J.encode(o),
        p.role and string.format(", role = %q", p.role) or "")
    end
  end
  parts[#parts + 1] = "} }\n"
  local src = table.concat(parts) .. H.readFile(H.ROOT .. "/" .. job.runner)

  local genv = E.getGlobalEnv()
  if not genv then
    -- a table without a Global script: run in a bare Global context
    genv = setmetatable({ self = E.Global }, { __index = E.G })
    genv._G = genv
  end
  local chunk, err = load(src, "=chunk_0", "t", genv)
  H.check("the relay runner compiles", chunk ~= nil, err)
  if not chunk then return end
  E.who("relay runner", "harness")
  local mark = #E.errors
  local ok, res = E.protect({ label = "relay runner", origin = "harness" }, chunk)
  H.check("the relay runner starts", ok, (not ok) and res or tostring(res))
  local seen = 0
  local done = nil
  local function drain()
    local ext = E.external or {}
    while seen < #ext do
      seen = seen + 1
      local m = ext[seen]
      if m.relay == "result" then H.check("relay: " .. tostring(m.name), m.ok, m.detail)
      elseif m.relay == "info" then H.info("relay: " .. tostring(m.message))
      elseif m.relay == "done" then done = m end
    end
    return done ~= nil
  end
  local finished = E.runUntil(drain, job.timeout_s or 360)
  drain()
  H.check("the relay runner reports done", finished, done and (done.passed .. " passed, " .. done.failed .. " failed") or "timed out")
  local errs = H.errorsSince(mark)
  H.check("no Lua errors while the relay suite ran", #errs == 0, #errs > 0 and H.describeErrors(errs) or nil)
  for _, e in ipairs(errs) do io.write("  [lua error] " .. tostring(e.trace) .. "\n") end
end
