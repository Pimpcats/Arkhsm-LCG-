-- Minimal JSON for the fake TTS (tests only). Decodes the object JSON the
-- relay spawns and GMNotes; encodes the messages TTS sends to the editor.
local M = {}

local escapes = { ['"'] = '\\"', ["\\"] = "\\\\", ["\b"] = "\\b", ["\f"] = "\\f",
                  ["\n"] = "\\n", ["\r"] = "\\r", ["\t"] = "\\t" }

local function isArray(t)
  local n = 0
  for k in pairs(t) do
    if type(k) ~= "number" then return false end
    n = n + 1
  end
  for i = 1, n do if t[i] == nil then return false end end
  return true
end

function M.encode(v)
  local t = type(v)
  if v == nil then return "null" end
  if t == "boolean" then return tostring(v) end
  if t == "number" then
    if v ~= v or v == math.huge or v == -math.huge then return "null" end
    if math.floor(v) == v and math.abs(v) < 1e15 then return string.format("%d", v) end
    return string.format("%.14g", v)
  end
  if t == "string" then
    return '"' .. v:gsub('[%c"\\]', function(c)
      return escapes[c] or string.format("\\u%04x", c:byte())
    end) .. '"'
  end
  if t == "table" then
    local parts = {}
    if next(v) ~= nil and isArray(v) then
      for i = 1, #v do parts[i] = M.encode(v[i]) end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    if next(v) == nil then return "{}" end
    for k, val in pairs(v) do
      if type(val) ~= "function" then
        parts[#parts + 1] = M.encode(tostring(k)) .. ":" .. M.encode(val)
      end
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  return "null"
end

local function utf8char(cp)
  if cp < 0x80 then return string.char(cp) end
  if cp < 0x800 then return string.char(0xC0 + math.floor(cp / 0x40), 0x80 + cp % 0x40) end
  if cp < 0x10000 then
    return string.char(0xE0 + math.floor(cp / 0x1000), 0x80 + math.floor(cp / 0x40) % 0x40, 0x80 + cp % 0x40)
  end
  return string.char(0xF0 + math.floor(cp / 0x40000), 0x80 + math.floor(cp / 0x1000) % 0x40,
    0x80 + math.floor(cp / 0x40) % 0x40, 0x80 + cp % 0x40)
end

function M.decode(s)
  local i = 1
  local function ws() i = s:find("[^ \t\r\n]", i) or (#s + 1) end
  local value
  local function str()
    i = i + 1
    local out = {}
    while true do
      local c = s:sub(i, i)
      if c == "" then error("unterminated string") end
      if c == '"' then i = i + 1 ; break end
      if c == "\\" then
        local e = s:sub(i + 1, i + 1)
        local map = { b = "\b", f = "\f", n = "\n", r = "\r", t = "\t", ['"'] = '"', ["\\"] = "\\", ["/"] = "/" }
        if e == "u" then
          local cp = tonumber(s:sub(i + 2, i + 5), 16)
          i = i + 6
          if cp >= 0xD800 and cp <= 0xDBFF and s:sub(i, i + 1) == "\\u" then
            local lo = tonumber(s:sub(i + 2, i + 5), 16)
            cp = 0x10000 + (cp - 0xD800) * 0x400 + (lo - 0xDC00)
            i = i + 6
          end
          out[#out + 1] = utf8char(cp)
        else
          out[#out + 1] = map[e] or e
          i = i + 2
        end
      else
        local j = s:find('["\\]', i) or (#s + 1)
        out[#out + 1] = s:sub(i, j - 1)
        i = j
      end
    end
    return table.concat(out)
  end
  function value()
    ws()
    local c = s:sub(i, i)
    if c == "{" then
      i = i + 1
      local t = {}
      ws()
      if s:sub(i, i) == "}" then i = i + 1 ; return t end
      while true do
        ws()
        local k = str()
        ws()
        assert(s:sub(i, i) == ":", "expected : at " .. i) ; i = i + 1
        t[k] = value()
        ws()
        local d = s:sub(i, i) ; i = i + 1
        if d == "}" then return t end
        assert(d == ",", "expected , at " .. i)
      end
    elseif c == "[" then
      i = i + 1
      local t = {}
      ws()
      if s:sub(i, i) == "]" then i = i + 1 ; return t end
      while true do
        t[#t + 1] = value()
        ws()
        local d = s:sub(i, i) ; i = i + 1
        if d == "]" then return t end
        assert(d == ",", "expected , at " .. i)
      end
    elseif c == '"' then
      return str()
    elseif s:sub(i, i + 3) == "true" then i = i + 4 ; return true
    elseif s:sub(i, i + 4) == "false" then i = i + 5 ; return false
    elseif s:sub(i, i + 3) == "null" then i = i + 4 ; return nil
    else
      local num = s:match("^-?%d+%.?%d*[eE]?[-+]?%d*", i)
      assert(num and #num > 0, "bad JSON at " .. i)
      i = i + #num
      return tonumber(num)
    end
  end
  return value()
end

return M
