-- The Still Hour's play engine (tools/play_engine/lua/engine.lua), unchanged, with one
-- metric added from outside for the Dunwich benchmark: skill tests counted by kind
-- (treachery, location, fight, ...), so "encounter-card tests failed" can be read the
-- same way for both campaigns. Nothing the engine decides is touched; only R.test is
-- wrapped to count its results. Used by tools/play_engine/official/benchmark.py.
return function(H)
  local engineFile = H.ROOT .. "/tools/play_engine/lua/engine.lua"
  H.args["suite-file"] = engineFile          -- engine.lua finds its modules next to itself
  local realDofile = dofile
  local function counted(flowModule)
    return function(R, T)
      flowModule(R, T)
      local base = R.test
      R.test = function(inv, skill, diff, opts)
        local ok, margin, tok = base(inv, skill, diff, opts)
        local m = R.G and R.G.metrics
        if m then
          local tk = m.tests_by_kind or {}
          m.tests_by_kind = tk
          local k = (opts and opts.kind) or "other"
          tk[k] = tk[k] or { n = 0, failed = 0 }
          tk[k].n = tk[k].n + 1
          if not ok then tk[k].failed = tk[k].failed + 1 end
        end
        return ok, margin, tok
      end
    end
  end
  dofile = function(path)
    local v = realDofile(path)
    if type(path) == "string" and path:match("[/\\]flow%.lua$") and type(v) == "function" then return counted(v) end
    return v
  end
  local suite = realDofile(engineFile)
  local ok, err = pcall(suite, H)
  dofile = realDofile
  if not ok then error(err, 0) end
end
