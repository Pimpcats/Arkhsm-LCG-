-- Every button, in every panel state, on SCED's real table (tests only; designer-facing).
--
-- The campaign is brought to each state the owner meets (the Prologue, a loop, Between Loops, the
-- Interlude panel during and after a night, the Setup panel, Part II, the finale and the finale with a
-- form down). In each, every button on the Control token is clicked, left and then right, each click
-- from the same saved campaign state (the Control's own save, restored before the click); in the
-- main states every button on the investigator cards and the campaign log's shown page is clicked too.
-- A click fails when it raises a Lua error (the campaign's or SCED's), leaves the Control's panel
-- empty, or puts the Control's state out of range.
--
-- tests/test_sced_buttons.py runs it on SCED's real table.

return function(H)
  local E, check, step, info = H.E, H.check, H.step, H.info
  local J = E.J

  local function decode(s)
    if type(s) ~= "string" or s == "" then return nil end
    local ok, v = pcall(J.decode, s)
    return ok and v or nil
  end
  local function gm(o) return decode(o.getGMNotes()) or {} end
  local function alive(o) return o ~= nil and not o.isDestroyed() end
  local function objects() return E.G.getObjects() end
  local function find(pred)
    for _, o in ipairs(objects()) do if alive(o) and pred(o) then return o end end
    return nil
  end
  local function findAll(pred)
    local l = {}
    for _, o in ipairs(objects()) do if alive(o) and pred(o) then l[#l + 1] = o end end
    return l
  end
  local function control()
    return find(function(o) return o.hasTag("StillHour") and tostring(o.getName()):find("Control", 1, true) ~= nil end)
  end
  local function st() return control().call("shApiState") end
  local function handler() return E.byGuid("123456") end
  local function sced(owner, kind) return handler().call("getObjectByOwnerAndType", { owner = owner, type = kind }) end
  local function logToken() return find(function(o) return o.hasTag("CampaignLog") end) end
  local function investigatorCards()
    return findAll(function(o) return o.type == "Card" and gm(o).type == "Investigator" and #(o.getButtons() or {}) > 0 end)
  end
  local function press(prefix, alt)
    local ctl = control()
    for _, b in ipairs(ctl.getButtons() or {}) do
      if tostring(b.label):sub(1, #prefix) == prefix then return E.click(ctl, b.index, "White", alt) end
    end
    return false
  end

  local MODES = { play = true, interlude = true, setup = true }
  local function sound()
    local ctl = control()
    if not ctl then return "the Control token is gone" end
    local s = st()
    if #(ctl.getButtons() or {}) == 0 then return "the panel is empty" end
    if not (s.hour >= 1 and s.hour <= 9) then return "hour " .. tostring(s.hour) end
    if not (s.dissonance >= 0 and s.dissonance <= 32) then return "dissonance " .. tostring(s.dissonance) end
    if not (s.memory >= 0) then return "memory " .. tostring(s.memory) end
    if not (s.stage >= 0 and s.stage <= 3) then return "approach " .. tostring(s.stage) end
    if not MODES[s.mode] then return "panel " .. tostring(s.mode) end
    return nil
  end

  local totals = { clicks = 0, buttons = 0, states = 0 }

  --- Click every button of `holder()` from the saved state, left and right; `enter` re-opens the panel.
  local function sweepButtons(state, what, holder, enter)
    local saved = control().call("onSave")
    local list = {}
    for _, b in ipairs(holder().getButtons() or {}) do
      if (b.width or 0) > 0 and b.click_function ~= "shNoop" then
        list[#list + 1] = { fn = b.click_function, label = tostring(b.label):gsub("\n", " ") }
      end
    end
    local bad = {}
    for _, b in ipairs(list) do
      for _, alt in ipairs({ false, true }) do
        control().call("shApiRestore", { blob = saved })
        enter()
        E.run(0.2)
        local o = holder()
        local idx
        for _, x in ipairs(o and o.getButtons() or {}) do if x.click_function == b.fn then idx = x.index end end
        if idx then
          local mark = #E.errors
          E.click(o, idx, "White", alt)
          E.run(1.5)
          totals.clicks = totals.clicks + 1
          local errs = H.errorsSince(mark)
          local why = #errs > 0 and H.describeErrors(errs, 1) or sound()
          if why then bad[#bad + 1] = string.format("'%s'%s: %s", b.label, alt and " (right)" or "", why) end
        end
      end
    end
    totals.buttons = totals.buttons + #list
    control().call("shApiRestore", { blob = saved })
    enter()
    E.run(0.5)
    check(string.format("%s: every %s button, left and right (%d buttons)", state, what, #list), #bad == 0,
      #bad > 0 and table.concat(bad, " || ", 1, math.min(#bad, 6)) or nil)
  end

  local function sweepState(state, enter, extras)
    step(state, function()
      enter()
      E.run(1)
      totals.states = totals.states + 1
      sweepButtons(state, "Control", control, enter)
      if extras then
        local cards = investigatorCards()
        for _, c in ipairs(cards) do
          local guid = c.getGUID()
          sweepButtons(state, "investigator card (" .. tostring(c.getName()) .. ")",
            function() return E.byGuid(guid) end, enter)
        end
        -- each of the log's three pages (right-click: Next page)
        for page = 1, 3 do
          if logToken() then sweepButtons(state, "campaign log page " .. page, logToken, enter) end
          local log = logToken()
          if log then E.menu(log, "Next page") ; E.run(1) end
        end
      end
    end)
  end

  ------------------------------------------------------------- the table --

  local payload = decode(H.readFile(H.payload or (H.ROOT .. "/dist/saved_object_the_still_hour.json")))
  local campaignBox = E.spawnData(payload.ObjectStates[1], {}, "campaign")
  step("buttons: the campaign laid out, two investigators seated, the Prologue set up", function()
    E.run(2) ; E.click(campaignBox, "Place", "White", false) ; E.run(4)
    local bag = sced("Mythos", "AllCardsBag")
    E.runUntil(function() return bag.call("isIndexReady") == true end, 120)
    press("Standard") ; E.run(1)
    control().call("shApiSeat", { ids = { "sthrelias", "sthrcass" } }) ; E.run(5)
    control().call("shApiSetUp") ; E.run(30)
    check("the Prologue is under way", st().prologue == true)
  end)

  local function main() control().call("shApiInterlude", { open = false }) end
  local function interlude() control().call("shApiInterlude", {}) end
  local function setupPanel() main() ; press("Set") end

  sweepState("the Prologue", main, true)
  sweepState("the Setup panel in the Prologue", setupPanel)
  step("buttons: on to loop 1", function()
    control().call("shApiEndPrologue") ; E.run(1)
    control().call("shApiSetUp", { again = true }) ; E.run(40)
    check("loop 1 is under way", st().prologue == false and st().loopEnded == false)
  end)
  sweepState("a loop", main, true)
  sweepState("the Setup panel during a loop", setupPanel)
  sweepState("the Interlude panel during a loop", interlude)
  step("buttons: the loop ends", function()
    control().call("shApiReset") ; E.run(2)
    check("Between Loops", st().loopEnded == true)
  end)
  sweepState("Between Loops", main, true)
  sweepState("the Interlude panel Between Loops", interlude)
  step("buttons: Part II, the next loop", function()
    control().call("shApiBeginNextLoop") ; E.run(1)
    control().call("shApiSetPartTwo", { on = true }) ; E.run(1)
    control().call("shApiSetUp", { again = true }) ; E.run(40)
    check("a Part II loop is under way", st().partTwo == true and st().loopEnded == false)
  end)
  sweepState("a Part II loop", main, true)
  step("buttons: the finale begins", function()
    control().call("shApiUnlockFact", { id = "the-way-the-night-breaks" }) ; E.run(1)
    control().call("shApiSetFinale", { on = true }) ; E.run(30)
    check("the finale is under way", st().finale == true)
  end)
  sweepState("the finale", main, true)
  step("buttons: a form is down", function()
    press("Forms defeated") ; E.run(1)
  end)
  sweepState("the finale with a form down", main)

  info(string.format("button sweep: %d clicks over %d buttons in %d states", totals.clicks, totals.buttons, totals.states))
  check("the sweep clicked buttons", totals.clicks > 0, totals.clicks)
end
