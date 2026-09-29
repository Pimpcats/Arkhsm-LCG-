-- Table snapshots for the Godot table renderer (tools/godot_table).
--
-- snapshot(E) describes every object on the emulated table the way a
-- renderer needs it: transform, TTS type, custom assets (card sheets, tile
-- and token images, meshes, asset bundles, PDFs), tint, lock/interactable,
-- decks (count, top and bottom card), bags (count), buttons and inputs as the
-- scripts created them, snap points, decals, 3D text and the object's own XML
-- UI; plus Global's current XML UI (attribute changes applied), snap points
-- and decals. Scripts, script states and GM notes are left out.
--
-- Snapshots are for the assistant's eyes only: tools/godot_table/render.py
-- writes them under .cache/ (gitignored).

local M = {}

local function num(v, d) v = tonumber(v) if v == nil or v ~= v then return d end return v end

local function vec(p, d)
  if type(p) ~= "table" then return d end
  return { num(p.x or p[1], 0), num(p.y or p[2], 0), num(p.z or p[3], 0) }
end

local function color(c)
  if type(c) == "string" then
    local E = M.E
    local col = E and E.Color.fromString(c)
    if col then return { col.r, col.g, col.b, col.a or 1 } end
    return nil
  end
  if type(c) ~= "table" then return nil end
  return { num(c.r or c[1], 1), num(c.g or c[2], 1), num(c.b or c[3], 1), num(c.a or c[4], 1) }
end

local function plain(v, depth)
  depth = depth or 0
  if type(v) ~= "table" then
    if type(v) == "function" or type(v) == "userdata" or type(v) == "thread" then return nil end
    return v
  end
  if depth > 12 then return nil end
  local t = {}
  for k, x in pairs(v) do
    if type(k) == "string" or type(k) == "number" then t[k] = plain(x, depth + 1) end
  end
  return t
end

local function customDeckFor(card, deckData)
  local id = num(card.CardID, 0)
  local deckId = math.floor(id / 100)
  local cd = card.CustomDeck or (deckData and deckData.CustomDeck) or {}
  local e = cd[tostring(deckId)] or cd[deckId]
  if not e then
    -- some saves key it by a different id: take the only entry
    local only
    for _, v in pairs(cd) do if only then only = nil break end only = v end
    e = only
  end
  if not e then return nil end
  return { FaceURL = e.FaceURL, BackURL = e.BackURL, NumWidth = num(e.NumWidth, 10), NumHeight = num(e.NumHeight, 7),
           BackIsHidden = e.BackIsHidden == true, UniqueBack = e.UniqueBack == true, Type = num(e.Type, 0) }
end

local function cardInfo(card, deckData)
  return { CardID = num(card.CardID, 0), Nickname = card.Nickname or "", SidewaysCard = card.SidewaysCard == true,
           CustomDeck = customDeckFor(card, deckData), Scale = card.Transform and { num(card.Transform.scaleX, 1),
             num(card.Transform.scaleY, 1), num(card.Transform.scaleZ, 1) } or nil }
end

local BUTTON_KEYS = { "label", "width", "height", "font_size", "tooltip", "click_function" }

local function buttonList(list)
  local out = {}
  for i, b in ipairs(list or {}) do
    local r = { index = i - 1 }
    for _, k in ipairs(BUTTON_KEYS) do if b[k] ~= nil then r[k] = type(b[k]) == "table" and nil or b[k] end end
    r.label = tostring(b.label or "")
    r.position = vec(b.position, { 0, 0, 0 })
    r.rotation = vec(b.rotation, { 0, 0, 0 })
    local s = b.scale
    if type(s) == "number" then s = { s, s, s } end
    r.scale = vec(s, { 1, 1, 1 })
    r.color = color(b.color) or { 1, 1, 1, 1 }
    r.font_color = color(b.font_color) or { 0, 0, 0, 1 }
    r.hover_color = color(b.hover_color)
    r.width = num(b.width, 100)
    r.height = num(b.height, 100)
    r.font_size = num(b.font_size, 100)
    out[#out + 1] = r
  end
  return out
end

local function inputList(list)
  local out = {}
  for i, b in ipairs(list or {}) do
    local s = b.scale
    if type(s) == "number" then s = { s, s, s } end
    out[#out + 1] = { index = i - 1, label = tostring(b.label or ""), value = tostring(b.value or ""),
      position = vec(b.position, { 0, 0, 0 }), rotation = vec(b.rotation, { 0, 0, 0 }), scale = vec(s, { 1, 1, 1 }),
      width = num(b.width, 100), height = num(b.height, 100), font_size = num(b.font_size, 100),
      color = color(b.color) or { 1, 1, 1, 1 }, font_color = color(b.font_color) or { 0, 0, 0, 1 },
      alignment = num(b.alignment, 1) }
  end
  return out
end

local function snaps(list)
  local out = {}
  for _, p in ipairs(list or {}) do
    local q = p.Position or p.position
    if q then
      local r = p.Rotation or p.rotation
      out[#out + 1] = { vec(q, { 0, 0, 0 }), r and vec(r, { 0, 0, 0 }) or false }
    end
  end
  return out
end

local function uiXml(ui)
  if not ui or not ui.getXml then return nil end
  local ok, x = pcall(ui.getXml)
  if ok and type(x) == "string" and x ~= "" then return x end
  return nil
end

-- the XML UI as TTS's UI.getXmlTable() form (attribute changes applied)
local function uiTable(ui)
  if not ui or not ui.getXmlTable then return nil end
  local ok, t = pcall(ui.getXmlTable)
  if ok and type(t) == "table" and #t > 0 then return plain(t) end
  return nil
end

function M.object(E, o)
  local st = E.S[o]
  local d = st.data
  local ty = E.typeOf(d.Name)
  local b = E.aabb(o)
  local r = {
    guid = st.guid, name = d.Name, type = ty, nickname = d.Nickname or "",
    pos = { st.pos.x, st.pos.y, st.pos.z }, rot = { st.rot.x, st.rot.y, st.rot.z },
    scale = { st.scale.x, st.scale.y, st.scale.z },
    locked = st.locked == true, interactable = o.interactable ~= false,
    tint = color(d.ColorDiffuse), origin = st.origin, hand = st.hand,
    bounds = { center = { b.center.x, b.center.y, b.center.z }, size = { b.size.x, b.size.y, b.size.z } },
    tags = o.getTags(), highlight = st.highlight and (color(st.highlight) or { 1, 1, 1, 1 }) or nil,
    face_down = o.is_face_down,
  }
  if E.sizeOverride[st.guid] then r.size_override = E.sizeOverride[st.guid] end
  if d.Name == "HandTrigger" then r.hand_color = d.FogColor end
  if d.Name == "Card" or d.Name == "CardCustom" then
    r.card = cardInfo(d)
    r.card.HideWhenFaceDown = d.HideWhenFaceDown
  elseif ty == "Deck" then
    local c = st.contained or {}
    r.deck = { count = #c, top = c[1] and cardInfo(c[1], d) or nil, bottom = c[#c] and cardInfo(c[#c], d) or nil }
  elseif ty == "Bag" or ty == "Infinite" then
    r.count = #(st.contained or {})
  end
  if d.CustomImage then
    local ci = d.CustomImage
    local ct = ci.CustomTile or {}
    local tok = ci.CustomToken or {}
    r.image = { ImageURL = ci.ImageURL, ImageSecondaryURL = ci.ImageSecondaryURL, ImageScalar = num(ci.ImageScalar, 1),
      WidthScale = num(ci.WidthScale, 0),
      tile = ci.CustomTile and { Type = num(ct.Type, 0), Thickness = num(ct.Thickness, 0.2),
        Stackable = ct.Stackable == true, Stretch = ct.Stretch ~= false } or nil,
      token = ci.CustomToken and { Thickness = num(tok.Thickness, 0.2), MergeDistancePixels = num(tok.MergeDistancePixels, 15),
        StandUp = tok.StandUp == true, Stackable = tok.Stackable == true } or nil }
  end
  if d.CustomMesh then
    local m = d.CustomMesh
    r.mesh = { MeshURL = m.MeshURL, DiffuseURL = m.DiffuseURL, NormalURL = m.NormalURL, ColliderURL = m.ColliderURL,
      MaterialIndex = num(m.MaterialIndex, 0), TypeIndex = num(m.TypeIndex, 0), CastShadows = m.CastShadows ~= false,
      Convex = m.Convex, CustomShader = plain(m.CustomShader) }
  end
  if d.CustomAssetbundle then
    local a = d.CustomAssetbundle
    r.bundle = { AssetbundleURL = a.AssetbundleURL, AssetbundleSecondaryURL = a.AssetbundleSecondaryURL,
      MaterialIndex = num(a.MaterialIndex, 0), TypeIndex = num(a.TypeIndex, 0), LoopingEffectIndex = num(a.LoopingEffectIndex, 0) }
  end
  if d.CustomPDF then
    r.pdf = { PDFUrl = d.CustomPDF.PDFUrl, PDFPage = num(st.book and st.book.page or d.CustomPDF.PDFPage, 0),
      PDFPageOffset = num(d.CustomPDF.PDFPageOffset, 0) }
  end
  if d.Text then r.text = plain(d.Text) end
  if d.AttachedDecals and #d.AttachedDecals > 0 then r.decals = plain(d.AttachedDecals) end
  if d.AttachedSnapPoints and #d.AttachedSnapPoints > 0 then r.snap_points = snaps(d.AttachedSnapPoints) end
  if d.RotationValues and #d.RotationValues > 0 then r.rotation_values = plain(d.RotationValues) end
  if #st.buttons > 0 then r.buttons = buttonList(st.buttons) end
  if #st.inputs > 0 then r.inputs = inputList(st.inputs) end
  -- the object's own (world-space) XML UI, as a table
  local xt = uiTable(st.ui)
  if xt then
    r.xml_table = xt
    -- the images / sprite bundles / fonts its UI refers to by name
    if type(d.CustomUIAssets) == "table" and #d.CustomUIAssets > 0 then r.ui_assets = plain(d.CustomUIAssets) end
  end
  if st.states then
    local n = 0
    for _ in pairs(st.states) do n = n + 1 end
    r.states = n + 1
    r.state_id = st.stateId
  end
  return r
end

--- The whole table (only objects on it; contents of bags and decks are summarised).
function M.snapshot(E, meta)
  M.E = E
  local objs = {}
  for _, o in ipairs(E.objects) do
    local st = E.S[o]
    if st and not st.removed and not st.inContainer then
      local ok, r = pcall(M.object, E, o)
      if ok then objs[#objs + 1] = r
      else objs[#objs + 1] = { guid = st.guid, name = st.data.Name, error = tostring(r) } end
    end
  end
  local g = E.Global
  local out = { meta = meta or {}, t = E.now, frame = E.frame, objects = objs,
    global = { xml_table = uiTable(g.UI), snap_points = snaps(g.getSnapPoints and g.getSnapPoints() or {}),
               decals = plain(g.getDecals and g.getDecals() or {}) } }
  return out
end

function M.write(E, path, meta)
  local s = E.J.encode(M.snapshot(E, meta))
  local f = assert(io.open(path, "wb"))
  f:write(s)
  f:close()
  return path
end

return M
