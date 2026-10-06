-- Each Hour change removes all doom in play, with SCED's own reset (tests only).
--
-- The guide asks the table to remove all doom in play whenever the Hourglass advances or rewinds.
-- On SCED the Control token's Hour button does it through the doom counter's startReset (the counter
-- goes to 0 and the doom tokens on the playmats and in the play area are removed); this suite checks
-- that, and that a click that changes no Hour resets nothing. Real SCED only: the stand-in has no
-- doom counter. tests/test_sced_hour_doom.py runs it.

return function(H)
  local E, check, step = H.E, H.check, H.step
  local J = E.J

  local function decode(s)
    if type(s) ~= "string" or s == "" then return nil end
    local ok, v = pcall(J.decode, s)
    return ok and v or nil
  end
  local function find(pred)
    for _, o in ipairs(E.G.getObjects()) do if pred(o) then return o end end
    return nil
  end
  local function control()
    return find(function(o) return o.hasTag("StillHour") and tostring(o.getName()):find("Control", 1, true) ~= nil end)
  end
  local function st() return control().call("shApiState") end
  local function click(o, which, alt)
    local ok, err = E.click(o, which, "White", alt)
    if not ok then check("button '" .. tostring(which) .. "' can be clicked", false, err) end
    return ok
  end
  local function counter()
    local handler = E.byGuid("123456")
    return handler and handler.call("getObjectByOwnerAndType", { owner = "Mythos", type = "DoomCounter" })
  end
  local function hourButton()
    for _, b in ipairs(control().getButtons()) do
      if tostring(b.label):find("^Hour %d") then return tostring(b.label) end
    end
  end
  local function chatSince(mark)
    local out = {}
    for i = mark + 1, #E.log do out[#out + 1] = tostring(E.log[i].msg) end
    return table.concat(out, " || ")
  end

  local payload = decode(H.readFile(H.payload or (H.ROOT .. "/dist/saved_object_the_still_hour.json")))
  local campaignBox = E.spawnData(payload.ObjectStates[1], {}, "campaign")

  step("setup: the campaign box laid out; SCED's doom counter is on the table", function()
    E.run(2); click(campaignBox, "Place"); E.run(4)
    click(control(), "Standard"); E.run(1)
    check("SCED's doom counter is found", counter() ~= nil)
    check("the Control token is at Hour I", st().hour == 1, st().hour)
  end)

  step("an advance removes the doom in play", function()
    counter().call("updateVal", 3); E.run(0.2)
    check("the counter shows 3 doom", counter().getVar("val") == 3, counter().getVar("val"))
    local mark = #E.log
    click(control(), hourButton()); E.run(1)
    check("the Hour advanced", st().hour == 2, st().hour)
    check("the doom counter is back to 0", counter().getVar("val") == 0, counter().getVar("val"))
    check("the table is told SCED did it, and what is left to do by hand",
      chatSince(mark):find("SCED removed the doom in play (take any doom off the Hours cards yourself)", 1, true) ~= nil,
      chatSince(mark):sub(-300))
  end)

  step("a rewind removes it too; a click that changes no Hour does not", function()
    counter().call("updateVal", 2); E.run(0.2)
    click(control(), hourButton(), true); E.run(1)                      -- right-click: rewind
    check("the Hour rewound to I", st().hour == 1, st().hour)
    check("the doom counter is back to 0", counter().getVar("val") == 0, counter().getVar("val"))
    counter().call("updateVal", 2); E.run(0.2)
    click(control(), hourButton(), true); E.run(1)                      -- the Hourglass never rewinds before Hour I
    check("the Hour stays at I", st().hour == 1, st().hour)
    check("nothing is removed when no Hour changed", counter().getVar("val") == 2, counter().getVar("val"))
  end)
end
