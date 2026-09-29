## Tabletop Simulator conventions used by the renderer.
##
## Space: TTS is Unity: left-handed, y up, positions in TTS units. Godot is
## right-handed. The renderer mirrors x: godot = (-x, y, z). A TTS rotation
## (Euler degrees, applied z, then x, then y) becomes
## Ry(-ry) * Rx(rx) * Rz(-rz) in Godot (the mirror conjugates each axis
## rotation). OBJ files (and UnityPy's mesh exports) are already mirrored the
## same way, so their vertices need no conversion.
##
## Images: a flat TTS object's image lies with its top towards local -z and
## its right towards local -x (TTS): towards -z and +x in Godot. The back
## (bottom face) is mirrored in u, so a flip about z shows it upright.


# Standard TTS card at scale 1 (x, z) and the thickness of one card.
const CARD_W := 2.2
const CARD_H := 3.1
const CARD_T := 0.02
const CARD_CORNER := 0.1

# createButton/createInput sizes are in "button units": world size =
# units * BUTTON_UNIT * object scale * button scale.
const BUTTON_UNIT := 0.002
# TTS draws a button's local x mirrored relative to the object's transform
# (positionToWorld); +1 would mean no mirror. Calibrated on SCED's playmat
# hot-spots (see docs/GODOT_TABLE.md).
const BUTTON_X := 1.0

# Custom_Tile at scale 1: the image's shorter side is TILE_SHORT units, the
# longer follows the aspect ratio. Custom_Token: its longer side is TOKEN_LONG.
const TILE_SHORT := 2.0
const TOKEN_LONG := 3.7

static func pos(p) -> Vector3:
	return Vector3(-float(p[0]), float(p[1]), float(p[2]))

static func basis(r) -> Basis:
	var rx := deg_to_rad(float(r[0]))
	var ry := deg_to_rad(float(r[1]))
	var rz := deg_to_rad(float(r[2]))
	return Basis(Vector3.UP, -ry) * Basis(Vector3.RIGHT, rx) * Basis(Vector3.BACK, -rz)

static func xform(p, r, s) -> Transform3D:
	var b := basis(r) * Basis.from_scale(Vector3(float(s[0]), float(s[1]), float(s[2])))
	return Transform3D(b, pos(p))

static func color(c, fallback: Color = Color.WHITE) -> Color:
	if c == null or not (c is Array) or c.size() < 3:
		return fallback
	var a := 1.0
	if c.size() > 3:
		a = float(c[3])
	return Color(float(c[0]), float(c[1]), float(c[2]), a)

static func norm_url(u) -> String:
	if u == null:
		return ""
	var s := String(u).strip_edges()
	for pre in ["{verifycache}", "{Unique}", "{unique}"]:
		if s.begins_with(pre):
			s = s.substr(pre.length())
	for old in ["http://cloud-3.steamusercontent.com", "https://cloud-3.steamusercontent.com",
			"http://steamusercontent-a.akamaihd.net"]:
		if s.begins_with(old):
			s = "https://steamusercontent-a.akamaihd.net" + s.substr(old.length())
	return s
