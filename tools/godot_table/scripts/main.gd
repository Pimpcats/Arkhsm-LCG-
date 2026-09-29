## Renders table snapshots (tests/sced_real snapshot.lua) to PNG.
##
##   godot --path tools/godot_table --rendering-driver opengl3 -- --job <job.json>
##
## job.json (written by tools/godot_table/render.py):
##   { manifest, scene: {sky, lighting}, width, height,
##     renders: [ { snapshot, options, shots: [ {out, camera} ] } ] }
## camera: {type: "persp", eye, target, fov} or
##         {type: "ortho", eye, target, size, up}; points in TTS coordinates.
## Each shot also writes <out>.json: the camera and every button's screen
## rectangle, so the assistant can check visibility and overlaps.
extends Node

const TTS = preload("res://scripts/tts.gd")
const ObjLoader = preload("res://scripts/obj_loader.gd")

var job: Dictionary
var man: Dictionary
var images: Dictionary
var crops: Dictionary
var meshes: Dictionary
var bundles: Dictionary
var pdfs: Dictionary

var tex_cache := {}
var obj_cache := {}
var mat_cache := {}
var prism_cache := {}

var vp: SubViewport
var world: Node3D
var cam: Camera3D
var sun: DirectionalLight3D
var envn: WorldEnvironment
var opts: Dictionary = {}
var button_nodes: Array = []     # [{obj, index, label, corners: [Vector3 x4]}]
var stats := {}
var pending: Array = []          # nodes placed in world space after a build

func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var job_path := ""
	for i in range(args.size()):
		if args[i] == "--job" and i + 1 < args.size():
			job_path = args[i + 1]
	if job_path == "":
		push_error("usage: -- --job <job.json>")
		get_tree().quit(2)
		return
	job = _read_json(job_path)
	man = _read_json(job.get("manifest", ""))
	images = man.get("images", {})
	crops = man.get("crops", {})
	meshes = man.get("meshes", {})
	bundles = man.get("bundles", {})
	pdfs = man.get("pdfs", {})
	_setup_viewport()
	_setup_scene(job.get("scene", {}))
	var t0 := Time.get_ticks_msec()
	var n := 0
	for r in job.get("renders", []):
		opts = r.get("options", {})
		var snap := _read_json(r["snapshot"])
		var tb := Time.get_ticks_msec()
		_build(snap)
		if r.has("ui") and FileAccess.file_exists(r["ui"]):
			_object_ui(JSON.parse_string(FileAccess.get_file_as_string(r["ui"])))
		var built_ms := Time.get_ticks_msec() - tb
		var first := true
		for shot in r.get("shots", []):
			_set_camera(shot["camera"])
			# a fresh build needs a frame to upload its textures
			for _i in range(2 if first else 1):
				await RenderingServer.frame_post_draw
			first = false
			var img := vp.get_texture().get_image()
			img.save_png(shot["out"])
			_write_shot_info(shot)
			n += 1
		print("RENDERED %s: %d objects, build %d ms" % [r["snapshot"].get_file(), snap.get("objects", []).size(), built_ms])
	print("DONE %d shots in %.1fs" % [n, (Time.get_ticks_msec() - t0) / 1000.0])
	if stats.size() > 0:
		print("STATS ", JSON.stringify(stats))
	get_tree().quit(0)

func _read_json(p: String) -> Dictionary:
	var f := FileAccess.open(p, FileAccess.READ)
	if f == null:
		push_error("cannot read " + p)
		return {}
	var d = JSON.parse_string(f.get_as_text())
	return d if d is Dictionary else {}

func _stat(k: String) -> void:
	stats[k] = int(stats.get(k, 0)) + 1

# ------------------------------------------------------------------ scene --

func _setup_viewport() -> void:
	vp = SubViewport.new()
	vp.size = Vector2i(int(job.get("width", 1920)), int(job.get("height", 1080)))
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.own_world_3d = true
	vp.msaa_3d = [Viewport.MSAA_DISABLED, Viewport.MSAA_2X, Viewport.MSAA_4X, Viewport.MSAA_8X][clampi(int(job.get("msaa", 2)), 0, 3)]
	if int(job.get("msaa", 2)) == 0:
		vp.screen_space_aa = Viewport.SCREEN_SPACE_AA_FXAA
	vp.positional_shadow_atlas_size = 0
	add_child(vp)
	cam = Camera3D.new()
	cam.near = 0.3
	cam.far = 2000.0
	vp.add_child(cam)
	cam.current = true

func _setup_scene(scene: Dictionary) -> void:
	var lt: Dictionary = scene.get("lighting", {})
	envn = WorldEnvironment.new()
	var e := Environment.new()
	var sky_url := TTS.norm_url(scene.get("sky_url", ""))
	var sky_tex := _texture(sky_url, false) if sky_url != "" else null
	if sky_tex != null:
		var sm := PanoramaSkyMaterial.new()
		sm.panorama = sky_tex
		var sky := Sky.new()
		sky.sky_material = sm
		e.sky = sky
		e.background_mode = Environment.BG_SKY
	else:
		e.background_mode = Environment.BG_COLOR
		e.background_color = Color(0.08, 0.08, 0.1)
	# TTS: AmbientType 0 = the background (sky) lights the table; 1 = gradient
	var amb_i := float(lt.get("AmbientIntensity", 1.3))
	var sky_c := TTS.color(_rgb(lt.get("AmbientSkyColor")), Color(0.5, 0.5, 0.5))
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = sky_c
	e.ambient_light_energy = amb_i * float(scene.get("ambient_gain", 0.55))
	e.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	e.tonemap_exposure = float(scene.get("exposure", 1.0))
	envn.environment = e
	vp.add_child(envn)
	sun = DirectionalLight3D.new()
	sun.light_color = TTS.color(_rgb(lt.get("LightColor")), Color(1, 0.98, 0.89))
	sun.light_energy = float(lt.get("LightIntensity", 0.54)) * float(scene.get("light_gain", 1.9))
	sun.shadow_enabled = bool(scene.get("shadows", true))
	sun.shadow_bias = 0.03
	sun.shadow_normal_bias = 1.0
	sun.directional_shadow_max_distance = 260.0
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_ORTHOGONAL
	sun.shadow_blur = 1.5
	# TTS's key light comes from high above, slightly from the far side
	var d: Array = scene.get("light_dir", [30.0, -80.0, 20.0])
	sun.transform = Transform3D(Basis(), Vector3.ZERO).looking_at(TTS.pos(d).normalized(), Vector3.UP if abs(float(d[1])) < 0.99 * TTS.pos(d).length() else Vector3.FORWARD)
	vp.add_child(sun)
	world = Node3D.new()
	vp.add_child(world)

func _rgb(d):
	if d is Dictionary:
		return [d.get("r", 1.0), d.get("g", 1.0), d.get("b", 1.0), 1.0]
	return d

func _set_camera(c: Dictionary) -> void:
	var eye := TTS.pos(c["eye"])
	var target := TTS.pos(c["target"])
	var up := Vector3.UP
	if c.has("up"):
		up = TTS.pos(c["up"]).normalized()
	if c.get("type", "persp") == "ortho":
		cam.projection = Camera3D.PROJECTION_ORTHOGONAL
		cam.size = float(c.get("size", 100.0))
	else:
		cam.projection = Camera3D.PROJECTION_PERSPECTIVE
		cam.fov = float(c.get("fov", 60.0))
		cam.keep_aspect = Camera3D.KEEP_HEIGHT
	cam.near = float(c.get("near", 0.3))
	cam.far = float(c.get("far", 2000.0))
	var t := Transform3D(Basis(), eye)
	cam.transform = t.looking_at(target, up)

func _write_shot_info(shot: Dictionary) -> void:
	var list := []
	var sz := Vector2(vp.size)
	for b in button_nodes:
		var pts := []
		var behind := false
		for p in b["corners"]:
			if cam.is_position_behind(p):
				behind = true
			var s := cam.unproject_position(p)
			pts.append([snappedf(s.x, 0.1), snappedf(s.y, 0.1)])
		if behind:
			continue
		var minx := 1e9
		var miny := 1e9
		var maxx := -1e9
		var maxy := -1e9
		for p in pts:
			minx = min(minx, p[0]); maxx = max(maxx, p[0])
			miny = min(miny, p[1]); maxy = max(maxy, p[1])
		if maxx < 0 or maxy < 0 or minx > sz.x or miny > sz.y:
			continue
		list.append({"guid": b["guid"], "kind": b["kind"], "index": b["index"], "label": b["label"],
			"visible_color": b["visible"], "rect": [minx, miny, maxx, maxy], "quad": pts, "top_y": b["top_y"]})
	var info := {"camera": shot["camera"], "size": [vp.size.x, vp.size.y], "buttons": list}
	var f := FileAccess.open(String(shot["out"]).get_basename() + ".json", FileAccess.WRITE)
	f.store_string(JSON.stringify(info))
	f.close()

# --------------------------------------------------------------- textures --

func _texture(url: String, mip: bool = true) -> Texture2D:
	if url == "":
		return null
	var k := url + ("#m" if mip else "")
	if tex_cache.has(k):
		return tex_cache[k]
	var rec = images.get(url)
	var tex: Texture2D = null
	if rec is Dictionary and rec.has("file"):
		tex = _load_tex(rec["file"], mip)
	tex_cache[k] = tex
	if tex == null:
		_stat("missing image")
	return tex

func _load_tex(file: String, mip: bool = true) -> Texture2D:
	var k := "file:" + file + ("#m" if mip else "")
	if tex_cache.has(k):
		return tex_cache[k]
	var img := Image.load_from_file(file)
	var tex: Texture2D = null
	if img != null and not img.is_empty():
		if mip:
			img.generate_mipmaps()
		tex = ImageTexture.create_from_image(img)
	tex_cache[k] = tex
	return tex

func _image_info(url: String) -> Dictionary:
	var rec = images.get(url)
	return rec if rec is Dictionary else {}

func _crop_tex(url: String, w: int, h: int, idx: int) -> Texture2D:
	var k := "%s#%d#%d#%d" % [TTS.norm_url(url), w, h, idx]
	var rec = crops.get(k)
	if rec is Dictionary and rec.has("file"):
		return _load_tex(rec["file"])
	_stat("missing card image")
	return null

# -------------------------------------------------------------- materials --

func _mat_image(tex: Texture2D, alpha_cut: bool = false, rough: float = 0.75, tint: Color = Color.WHITE, uv_xform = null) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = tint
	if tex != null:
		m.albedo_texture = tex
	m.roughness = rough
	m.metallic_specular = 0.3
	m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	if alpha_cut:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		m.alpha_scissor_threshold = 0.5
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
	if uv_xform != null:
		m.uv1_scale = uv_xform[0]
		m.uv1_offset = uv_xform[1]
	return m

func _mat_color(c: Color, rough: float = 0.7) -> StandardMaterial3D:
	var k := "c:%s:%f" % [c.to_html(true), rough]
	if mat_cache.has(k):
		return mat_cache[k]
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rough
	if c.a < 0.999:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat_cache[k] = m
	return m

# ------------------------------------------------------------------ meshes --

## Outline (x, z) of a shape, clockwise seen from above (Godot's front face).
func _outline(kind: String, w: float, h: float, r: float = 0.0, seg: int = 6) -> PackedVector2Array:
	var pts := PackedVector2Array()
	if kind == "ellipse":
		var n := 64
		for i in range(n):
			var a := -PI / 2 + TAU * i / n
			pts.append(Vector2(cos(a) * w / 2, sin(a) * h / 2))
		return pts
	if kind == "hex":
		for i in range(6):
			var a := TAU * i / 6.0
			pts.append(Vector2(cos(a) * w / 2, sin(a) * h / 2))
		return pts
	r = clamp(r, 0.0, min(w, h) / 2)
	if r <= 0.0001:
		return PackedVector2Array([Vector2(-w / 2, -h / 2), Vector2(w / 2, -h / 2), Vector2(w / 2, h / 2), Vector2(-w / 2, h / 2)])
	var cs := [Vector2(w / 2 - r, -h / 2 + r), Vector2(w / 2 - r, h / 2 - r), Vector2(-w / 2 + r, h / 2 - r), Vector2(-w / 2 + r, -h / 2 + r)]
	var start := [-PI / 2, 0.0, PI / 2, PI]
	for c in range(4):
		for i in range(seg + 1):
			var a: float = start[c] + (PI / 2) * i / seg
			pts.append(cs[c] + Vector2(cos(a), sin(a)) * r)
	return pts

## A flat prism: surface 0 = top (+y, image upright), 1 = bottom (-y, u
## mirrored), 2 = sides. Size w (x) by h (z), thickness t.
func _prism(kind: String, w: float, h: float, t: float, r: float = 0.0) -> ArrayMesh:
	var k := "%s:%.4f:%.4f:%.4f:%.4f" % [kind, w, h, t, r]
	if prism_cache.has(k):
		return prism_cache[k]
	var pts := _outline(kind, w, h, r)
	var mesh := ArrayMesh.new()
	for face_v in [1, -1]:
		var face: int = face_v
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var y: float = face * t / 2.0
		var n := pts.size()
		for i in range(n):
			var a := pts[i]
			var b := pts[(i + 1) % n]
			var tri := [Vector2.ZERO, a, b] if face == 1 else [Vector2.ZERO, b, a]
			for p in tri:
				var u: float = (p.x + w / 2) / w
				if face == -1:
					u = 1.0 - u
				st.set_normal(Vector3(0, face, 0))
				st.set_uv(Vector2(u, (p.y + h / 2) / h))
				st.add_vertex(Vector3(p.x, y, p.y))
		st.generate_tangents()
		st.commit(mesh)
	var ss := SurfaceTool.new()
	ss.begin(Mesh.PRIMITIVE_TRIANGLES)
	var m := pts.size()
	var per := 0.0
	for i in range(m):
		per += pts[i].distance_to(pts[(i + 1) % m])
	var acc := 0.0
	for i in range(m):
		var a := pts[i]
		var b := pts[(i + 1) % m]
		var d := b - a
		var nrm := Vector3(d.y, 0, -d.x).normalized()
		var ta := Vector3(a.x, t / 2, a.y)
		var tb := Vector3(b.x, t / 2, b.y)
		var ba := Vector3(a.x, -t / 2, a.y)
		var bb := Vector3(b.x, -t / 2, b.y)
		var u0 := acc / per
		acc += d.length()
		var u1 := acc / per
		for v in [[tb, u1, 0.0], [ta, u0, 0.0], [ba, u0, 1.0], [tb, u1, 0.0], [ba, u0, 1.0], [bb, u1, 1.0]]:
			ss.set_normal(nrm)
			ss.set_uv(Vector2(v[1], v[2]))
			ss.add_vertex(v[0])
	ss.commit(mesh)
	prism_cache[k] = mesh
	return mesh

func _quad(w: float, h: float, up: bool = true) -> ArrayMesh:
	var k := "quad:%.4f:%.4f:%s" % [w, h, up]
	if prism_cache.has(k):
		return prism_cache[k]
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var pts := [Vector2(-w / 2, -h / 2), Vector2(w / 2, -h / 2), Vector2(w / 2, h / 2), Vector2(-w / 2, h / 2)]
	var tris := [[0, 1, 2], [0, 2, 3]] if up else [[0, 2, 1], [0, 3, 2]]
	for tri in tris:
		for i in tri:
			var p: Vector2 = pts[i]
			var u: float = (p.x + w / 2) / w
			if not up:
				u = 1.0 - u
			st.set_normal(Vector3(0, 1 if up else -1, 0))
			st.set_uv(Vector2(u, (p.y + h / 2) / h))
			st.add_vertex(Vector3(p.x, 0, p.y))
	var mesh := st.commit()
	prism_cache[k] = mesh
	return mesh

func _obj_mesh(file: String) -> ArrayMesh:
	if obj_cache.has(file):
		return obj_cache[file]
	var m := ObjLoader.load_obj(file, true)
	obj_cache[file] = m
	return m

# ---------------------------------------------------------------- building --

var nodes_by_guid := {}

func _build(snap: Dictionary) -> void:
	for c in world.get_children():
		world.remove_child(c)
		c.queue_free()
	button_nodes.clear()
	pending.clear()
	nodes_by_guid.clear()
	var hands := {}          # color -> [card objects]
	var zones := {}          # color -> hand zone object
	for o in snap.get("objects", []):
		if o.has("error"):
			_stat("snapshot error")
			continue
		if o.get("hand_color", null) != null:
			zones[o["hand_color"]] = o
		if o.get("hand", null) != null:
			if not hands.has(o["hand"]):
				hands[o["hand"]] = []
			hands[o["hand"]].append(o)
			continue
		var node := _object(o)
		if node == null:
			continue
		node.name = "%s_%s" % [o.get("name", "?"), o.get("guid", "?")]
		world.add_child(node)
		nodes_by_guid[o.get("guid", "")] = node
		_buttons(o, node)
	for color in hands:
		_hand(hands[color], zones.get(color, {}))
	for p in pending:
		world.add_child(p)
	if opts.get("global_snap_points", false):
		var gs: Array = snap.get("global", {}).get("snap_points", [])
		for sp in gs:
			world.add_child(_snap_marker(TTS.pos(sp[0]), Color(0.2, 1, 1)))

func _object(o: Dictionary) -> Node3D:
	var name: String = o.get("name", "")
	var ty: String = o.get("type", "")
	if o.get("hand", null) != null:
		_stat("in a hand (not drawn)")
		return null
	var root := Node3D.new()
	root.transform = TTS.xform(o["pos"], o["rot"], o["scale"])
	var body: Node3D = null
	if name == "Card" or name == "CardCustom":
		body = _card(o)
	elif ty == "Deck":
		body = _deck(o)
	elif name == "Custom_Tile" or name == "Custom_Tile_Stack":
		body = _tile(o)
	elif name == "Custom_Token" or name == "Custom_Token_Stack":
		body = _token(o)
	elif o.has("mesh"):
		body = _model(o)
	elif o.has("bundle"):
		body = _bundle(o)
	elif name == "Custom_PDF":
		body = _pdf(o)
	elif name == "3DText":
		body = _text3d(o)
	elif name == "HandTrigger":
		body = _zone_box(o, TTS.color(o.get("tint"), Color.WHITE), 0.18)
	elif name == "FogOfWarTrigger":
		body = _zone_box(o, Color(0.2, 0.2, 0.22), 0.93)
	elif ty == "Scripting" or ty == "Layout" or name == "RandomizeTrigger":
		if opts.get("zones", false):
			body = _zone_box(o, Color(0.3, 1.0, 0.3), 0.12)
		else:
			return null
	else:
		body = _primitive(o)
	if body == null:
		_stat("not drawn: " + name)
		return null
	root.add_child(body)
	if opts.get("snap_points", false):
		for sp in o.get("snap_points", []):
			# markers keep one world size: placed in world space
			pending.append(_snap_marker(root.transform * TTS.pos(sp[0]), Color(1, 0, 1)))
	return root

## Cards in a player's hand: TTS shows them standing in a row in the hand
## zone, faces towards the seat, leaning back a little.
func _hand(cards: Array, zone: Dictionary) -> void:
	if zone.is_empty():
		_stat("hand without a zone")
		return
	var zt := TTS.xform(zone["pos"], zone["rot"], [1, 1, 1])
	var width := float(zone["scale"][0])
	var fwd := (zt.basis * Vector3(0, 0, 1)).normalized()   # TTS local +z: towards the table
	var right := fwd.cross(Vector3.UP).normalized()
	var tilt := deg_to_rad(18.0)
	var up := (Vector3.UP * cos(tilt) + fwd * sin(tilt)).normalized()
	var normal := right.cross(up).normalized()
	var n := cards.size()
	var step: float = min(TTS.CARD_W * 1.05, width * 0.9 / max(1, n))
	var base := zt.origin + Vector3(0, float(zone["scale"][1]) * -0.1, 0)
	for i in range(n):
		var o: Dictionary = cards[i]
		var root := Node3D.new()
		var sc := float(o["scale"][0])
		var b := Basis(right, normal, -up) * Basis.from_scale(Vector3(sc, 1, sc))
		root.transform = Transform3D(b, base + right * (step * (i - (n - 1) / 2.0)) - fwd * 0.02 * i)
		var body := _card(o)
		root.add_child(body)
		world.add_child(root)
		nodes_by_guid[o.get("guid", "")] = root

## Objects' XML UI (tools/godot_table/object_ui.py drew each panel).
func _object_ui(items) -> void:
	if not (items is Array):
		return
	for it in items:
		if not (it is Dictionary) or not it.has("file"):
			continue
		var node: Node3D = nodes_by_guid.get(it.get("guid", ""), null)
		if node == null:
			continue
		var tex := _load_tex(it["file"], false)
		if tex == null:
			continue
		var q := MeshInstance3D.new()
		q.mesh = _quad(float(it["size"][0]), float(it["size"][1]))
		var m := StandardMaterial3D.new()
		m.albedo_texture = tex
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.cull_mode = BaseMaterial3D.CULL_DISABLED
		m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR
		m.render_priority = 1
		q.material_override = m
		q.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		var c: Array = it["center"]
		q.position = TTS.pos([c[0], float(c[1]) + 0.002, c[2]])
		node.add_child(q)
		_stat("object ui panels")

func _snap_marker(p: Vector3, c: Color) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.25
	sm.height = 0.5
	mi.mesh = sm
	var m := _mat_color(c, 1.0)
	m.no_depth_test = true
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mi.material_override = m
	mi.position = p
	return mi

func _edge_color(o: Dictionary) -> Color:
	# the sides of cards/tiles: TTS shows a pale card edge / the tint
	var c := TTS.color(o.get("tint"), Color(0.85, 0.85, 0.82))
	if c.r + c.g + c.b < 0.05:
		return Color(0.12, 0.12, 0.12)
	return Color(c.r, c.g, c.b, 1.0)

func _card_face_tex(ci: Dictionary, back: bool) -> Texture2D:
	var cd = ci.get("CustomDeck")
	if not (cd is Dictionary):
		return null
	var idx: int = int(ci.get("CardID", 0)) % 100
	var w := int(cd.get("NumWidth", 10))
	var h := int(cd.get("NumHeight", 7))
	if back:
		var bu := TTS.norm_url(cd.get("BackURL", ""))
		if cd.get("UniqueBack", false):
			return _crop_tex(bu, w, h, idx)
		return _texture(bu)
	return _crop_tex(TTS.norm_url(cd.get("FaceURL", "")), w, h, idx)

func _sideways(ci: Dictionary):
	# a sideways card's landscape image is laid along the card's long side
	return ci.get("SidewaysCard", false)

func _card_mat(tex: Texture2D, sideways: bool, bottom: bool) -> Material:
	if tex == null:
		return _mat_color(Color(0.55, 0.55, 0.6))
	if not sideways:
		return _mat_image(tex, false, 0.6)
	var sm := ShaderMaterial.new()
	sm.shader = _sideways_shader()
	sm.set_shader_parameter("tex", tex)
	sm.set_shader_parameter("mirror", bottom)
	return sm

var _sw_shader: Shader
func _sideways_shader() -> Shader:
	if _sw_shader == null:
		_sw_shader = Shader.new()
		_sw_shader.code = """
shader_type spatial;
uniform sampler2D tex : source_color, filter_linear_mipmap_anisotropic;
uniform bool mirror = false;
void fragment() {
	vec2 uv = UV;
	if (mirror) { uv.x = 1.0 - uv.x; }
	// landscape image rotated a quarter turn onto the portrait card
	vec2 r = vec2(uv.y, 1.0 - uv.x);
	if (mirror) { r.x = 1.0 - r.x; }
	ALBEDO = texture(tex, r).rgb;
	ROUGHNESS = 0.6;
	SPECULAR = 0.3;
}
"""
	return _sw_shader

func _card(o: Dictionary) -> Node3D:
	var ci: Dictionary = o.get("card", {})
	var mi := MeshInstance3D.new()
	mi.mesh = _prism("rect", TTS.CARD_W, TTS.CARD_H, TTS.CARD_T, TTS.CARD_CORNER)
	var sw: bool = _sideways(ci)
	mi.set_surface_override_material(0, _card_mat(_card_face_tex(ci, false), sw, false))
	mi.set_surface_override_material(1, _card_mat(_card_face_tex(ci, true), sw, true))
	mi.set_surface_override_material(2, _mat_color(Color(0.8, 0.8, 0.78)))
	return mi

func _deck(o: Dictionary) -> Node3D:
	var dk: Dictionary = o.get("deck", {})
	var n: int = max(1, int(dk.get("count", 1)))
	var t: float = max(TTS.CARD_T, TTS.CARD_T * n)
	var mi := MeshInstance3D.new()
	mi.mesh = _prism("rect", TTS.CARD_W, TTS.CARD_H, t, TTS.CARD_CORNER)
	var top: Dictionary = dk.get("top", {}) if dk.get("top") is Dictionary else {}
	var bottom: Dictionary = dk.get("bottom", {}) if dk.get("bottom") is Dictionary else top
	# the deck's list runs from local -y (top when face down) to local +y
	mi.set_surface_override_material(0, _card_mat(_card_face_tex(bottom, false), _sideways(bottom), false))
	mi.set_surface_override_material(1, _card_mat(_card_face_tex(top, true), _sideways(top), true))
	mi.set_surface_override_material(2, _mat_color(Color(0.78, 0.78, 0.75)))
	return mi

func _tile_size(url: String, fallback: Vector2) -> Vector2:
	var info := _image_info(url)
	var s = info.get("orig_size", null)
	if not (s is Array) or s.size() < 2 or float(s[1]) <= 0:
		return fallback
	var a: float = float(s[0]) / float(s[1])
	if a >= 1.0:
		return Vector2(TTS.TILE_SHORT * a, TTS.TILE_SHORT)
	return Vector2(TTS.TILE_SHORT, TTS.TILE_SHORT / a)

func _tile(o: Dictionary) -> Node3D:
	var im: Dictionary = o.get("image", {})
	var url := TTS.norm_url(im.get("ImageURL", ""))
	var tile: Dictionary = im.get("tile", {}) if im.get("tile") is Dictionary else {}
	var ttype := int(tile.get("Type", 0))
	var t := float(tile.get("Thickness", 0.2))
	var sz := _tile_size(url, Vector2(2, 2))
	var kind := "rect"
	var r := 0.0
	if ttype == 1:
		kind = "hex"
		sz = Vector2(max(sz.x, sz.y), max(sz.x, sz.y))
	elif ttype == 2:
		kind = "ellipse"
	elif ttype == 3:
		r = min(sz.x, sz.y) * 0.08
	var mi := MeshInstance3D.new()
	mi.mesh = _prism(kind, sz.x, sz.y, t, r)
	var tex := _texture(url)
	var info := _image_info(url)
	var alpha: bool = info.get("alpha", false)
	mi.set_surface_override_material(0, _mat_image(tex, alpha, 0.7))
	var back_url := TTS.norm_url(im.get("ImageSecondaryURL", ""))
	var back := _texture(back_url) if back_url != "" else tex
	mi.set_surface_override_material(1, _mat_image(back, alpha, 0.7))
	mi.set_surface_override_material(2, _mat_color(_edge_color(o)))
	if tex == null:
		mi.set_surface_override_material(0, _mat_color(Color(0.4, 0.4, 0.45)))
	return mi

func _token(o: Dictionary) -> Node3D:
	var im: Dictionary = o.get("image", {})
	var url := TTS.norm_url(im.get("ImageURL", ""))
	var tok: Dictionary = im.get("token", {}) if im.get("token") is Dictionary else {}
	var t := float(tok.get("Thickness", 0.2))
	var info := _image_info(url)
	var s = info.get("orig_size", [1, 1])
	var a: float = float(s[0]) / max(1.0, float(s[1]))
	var sz := Vector2(TTS.TOKEN_LONG, TTS.TOKEN_LONG / a) if a >= 1.0 else Vector2(TTS.TOKEN_LONG * a, TTS.TOKEN_LONG)
	sz *= float(im.get("ImageScalar", 1.0))
	var tex := _texture(url)
	var back_url := TTS.norm_url(im.get("ImageSecondaryURL", ""))
	var back := _texture(back_url) if back_url != "" else tex
	var alpha: bool = info.get("alpha", false)
	if tok.get("StandUp", false):
		pass
	if not alpha:
		var mi := MeshInstance3D.new()
		mi.mesh = _prism("rect", sz.x, sz.y, t)
		mi.set_surface_override_material(0, _mat_image(tex, false, 0.7))
		mi.set_surface_override_material(1, _mat_image(back, false, 0.7))
		mi.set_surface_override_material(2, _mat_color(Color(0.2, 0.2, 0.2)))
		return mi
	# TTS extrudes a token from its image's alpha: the cut-out is drawn as
	# stacked alpha-tested layers (top, bottom, and darkened slices between)
	var root := Node3D.new()
	var layers := 4
	for i in range(layers + 1):
		var f := float(i) / layers
		var y := -t / 2 + t * f
		var up := i == layers
		var down := i == 0
		var q := MeshInstance3D.new()
		q.mesh = _quad(sz.x, sz.y, not down)
		q.position = Vector3(0, y, 0)
		var m: StandardMaterial3D
		if up:
			m = _mat_image(tex, true, 0.7)
		elif down:
			m = _mat_image(back, true, 0.7)
		else:
			m = _mat_image(tex, true, 0.9, Color(0.35, 0.35, 0.35))
		q.material_override = m
		root.add_child(q)
	return root

func _model_material(o: Dictionary, m: Dictionary) -> StandardMaterial3D:
	var tex := _texture(TTS.norm_url(m.get("DiffuseURL", "")))
	var tint := TTS.color(o.get("tint"), Color.WHITE)
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(tint.r, tint.g, tint.b, 1.0)
	if tex != null:
		mat.albedo_texture = tex
	var info := _image_info(TTS.norm_url(m.get("DiffuseURL", "")))
	if info.get("alpha", false):
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_DEPTH_PRE_PASS
	var nurl := TTS.norm_url(m.get("NormalURL", ""))
	if nurl != "":
		var nt := _texture(nurl)
		if nt != null:
			mat.normal_enabled = true
			mat.normal_texture = nt
	# TTS materials: 0 plastic, 1 wood, 2 metal, 3 cardboard
	match int(m.get("MaterialIndex", 0)):
		0:
			mat.roughness = 0.35
			mat.metallic_specular = 0.5
		1:
			mat.roughness = 0.7
			mat.metallic_specular = 0.3
		2:
			mat.roughness = 0.3
			mat.metallic = 0.7
		3:
			mat.roughness = 0.9
			mat.metallic_specular = 0.15
	var sh = m.get("CustomShader")
	if sh is Dictionary:
		var si := float(sh.get("SpecularIntensity", 0.0))
		var ss := float(sh.get("SpecularSharpness", 2.0))
		if si <= 0.001:
			mat.metallic_specular = min(mat.metallic_specular, 0.15)
		else:
			mat.metallic_specular = clamp(si, 0.0, 1.0)
			mat.roughness = clamp(1.0 - (ss - 2.0) / 6.0, 0.15, 1.0)
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return mat

func _model(o: Dictionary) -> Node3D:
	var m: Dictionary = o["mesh"]
	var rec = meshes.get(TTS.norm_url(m.get("MeshURL", "")))
	if not (rec is Dictionary) or not rec.has("file"):
		_stat("missing mesh")
		return _primitive(o)
	var mesh := _obj_mesh(rec["file"])
	if mesh == null or mesh.get_surface_count() == 0:
		_stat("bad mesh")
		return _primitive(o)
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = _model_material(o, m)
	if not m.get("CastShadows", true):
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi

func _bundle(o: Dictionary) -> Node3D:
	var b: Dictionary = o["bundle"]
	var rec = bundles.get(TTS.norm_url(b.get("AssetbundleURL", "")))
	if not (rec is Dictionary) or rec.get("parts", []).size() == 0:
		_stat("bundle placeholder")
		return _placeholder(o, "asset bundle")
	var root := Node3D.new()
	for p in rec["parts"]:
		if not p.get("active", true) or not p.get("enabled", true):
			continue
		var mesh := _obj_mesh(p["obj"])
		if mesh == null:
			continue
		var mi := MeshInstance3D.new()
		mi.mesh = mesh
		var tr = p.get("transform")
		if tr is Array and tr.size() == 12:
			mi.transform = Transform3D(Vector3(tr[0], tr[1], tr[2]), Vector3(tr[3], tr[4], tr[5]),
				Vector3(tr[6], tr[7], tr[8]), Vector3(tr[9], tr[10], tr[11]))
		var mats: Array = p.get("materials", [])
		for si in range(mesh.get_surface_count()):
			var md: Dictionary = mats[min(si, mats.size() - 1)] if mats.size() > 0 else {}
			mi.set_surface_override_material(si, _bundle_material(o, md))
		root.add_child(mi)
	return root

func _bundle_material(o: Dictionary, md: Dictionary) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	var c := TTS.color(md.get("color"), Color.WHITE)
	var tint := TTS.color(o.get("tint"), Color.WHITE)
	mat.albedo_color = Color(c.r * tint.r, c.g * tint.g, c.b * tint.b, 1.0)
	if md.has("albedo"):
		mat.albedo_texture = _load_tex(md["albedo"])
		var s = md.get("uv_scale", [1, 1])
		var off = md.get("uv_offset", [0, 0])
		mat.uv1_scale = Vector3(float(s[0]), float(s[1]), 1)
		mat.uv1_offset = Vector3(float(off[0]), float(off[1]), 0)
	if md.has("normal"):
		mat.normal_enabled = true
		mat.normal_texture = _load_tex(md["normal"])
	mat.metallic = clamp(float(md.get("metallic", 0.0)), 0.0, 1.0)
	mat.roughness = clamp(1.0 - float(md.get("glossiness", 0.4)), 0.05, 1.0)
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return mat

func _pdf(o: Dictionary) -> Node3D:
	var p: Dictionary = o.get("pdf", {})
	var rec = pdfs.get(TTS.norm_url(p.get("PDFUrl", "")))
	var aspect := 0.77
	var tex: Texture2D = null
	if rec is Dictionary and rec.has("file"):
		tex = _load_tex(rec["file"])
		var s = rec.get("size", [770, 1000])
		aspect = float(s[0]) / max(1.0, float(s[1]))
	var w := 2.0
	var h := 2.0 / aspect
	var mi := MeshInstance3D.new()
	mi.mesh = _prism("rect", w, h, 0.1)
	mi.set_surface_override_material(0, _mat_image(tex, false, 0.8) if tex != null else _mat_color(Color(0.9, 0.88, 0.8)))
	mi.set_surface_override_material(1, _mat_color(Color(0.2, 0.2, 0.2)))
	mi.set_surface_override_material(2, _mat_color(Color(0.95, 0.95, 0.92)))
	return mi

func _text3d(o: Dictionary) -> Node3D:
	var td: Dictionary = o.get("text", {})
	var l := Label3D.new()
	l.text = String(td.get("Text", ""))
	var fs := float(td.get("fontSize", 64))
	l.font_size = 96
	# TTS 3D text: fontSize 64 is about one unit tall
	l.pixel_size = fs / 64.0 * 1.0 / 96.0
	var cs = td.get("colorstate")
	l.modulate = TTS.color(_rgb(cs), Color.WHITE) if cs is Dictionary else Color.WHITE
	l.shaded = false
	l.double_sided = false
	l.outline_size = 0
	l.rotation = Vector3(-PI / 2, 0, 0)
	var n := Node3D.new()
	n.add_child(l)
	return n

func _zone_box(o: Dictionary, c: Color, alpha: float) -> Node3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3.ONE
	mi.mesh = bm
	mi.material_override = _mat_color(Color(c.r, c.g, c.b, alpha), 1.0)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi

func _placeholder(o: Dictionary, what: String) -> Node3D:
	var n := Node3D.new()
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = Vector3(1, 1, 1)
	mi.mesh = bm
	mi.material_override = _mat_color(Color(0.8, 0.2, 0.8, 0.6))
	n.add_child(mi)
	var l := Label3D.new()
	l.text = what + "\n" + String(o.get("nickname", ""))
	l.pixel_size = 0.01
	l.position = Vector3(0, 0.8, 0)
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	n.add_child(l)
	return n

func _primitive(o: Dictionary) -> Node3D:
	var name: String = o.get("name", "")
	var tint := TTS.color(o.get("tint"), Color(0.8, 0.8, 0.8))
	var mi := MeshInstance3D.new()
	if name == "BlockRectangle":
		var bm := BoxMesh.new()
		bm.size = Vector3(2, 1, 1)
		mi.mesh = bm
	elif name.begins_with("Block") or name == "Custom_Dice" or name.begins_with("Die_"):
		var bm := BoxMesh.new()
		bm.size = Vector3.ONE
		mi.mesh = bm
	elif name == "Bag" or name == "Infinite_Bag":
		var cm := CylinderMesh.new()
		cm.top_radius = 0.55
		cm.bottom_radius = 0.75
		cm.height = 1.4
		mi.mesh = cm
		mi.position = Vector3(0, 0.1, 0)
	elif name.begins_with("Checker") or name.begins_with("go_game") or name.begins_with("Chip") or name.begins_with("Chinese"):
		var cm := CylinderMesh.new()
		cm.top_radius = 0.45
		cm.bottom_radius = 0.45
		cm.height = 0.25
		mi.mesh = cm
		if name.ends_with("black"):
			tint = Color(0.1, 0.1, 0.1)
		elif name.contains("white"):
			tint = Color(0.92, 0.92, 0.9)
	else:
		var bm := BoxMesh.new()
		bm.size = Vector3(1, 0.4, 1)
		mi.mesh = bm
		_stat("generic box: " + name)
	mi.material_override = _mat_color(tint, 0.6)
	return mi

# ---------------------------------------------------------------- buttons --

func _buttons(o: Dictionary, node: Node3D) -> void:
	for kind in ["buttons", "inputs"]:
		for b in o.get(kind, []):
			_button(o, node, b, kind == "inputs")

func _button(o: Dictionary, node: Node3D, b: Dictionary, is_input: bool) -> void:
	var p: Array = b.get("position", [0, 0, 0])
	var r: Array = b.get("rotation", [0, 0, 0])
	var s: Array = b.get("scale", [1, 1, 1])
	var w := float(b.get("width", 100)) * TTS.BUTTON_UNIT
	var h := float(b.get("height", 100)) * TTS.BUTTON_UNIT
	var col := TTS.color(b.get("color"), Color.WHITE)
	var fcol := TTS.color(b.get("font_color"), Color.BLACK)
	var label := String(b.get("label", ""))
	if is_input:
		var v := String(b.get("value", ""))
		if v != "":
			label = v
	var bn := Node3D.new()
	# button space: object local, mirrored in x (TTS quirk), own rotation/scale
	bn.transform = TTS.xform([float(p[0]) * TTS.BUTTON_X, p[1], p[2]],
		[r[0], float(r[1]) * TTS.BUTTON_X, float(r[2]) * TTS.BUTTON_X], s)
	node.add_child(bn)
	var visible := col.a > 0.01 and w > 0.0001 and h > 0.0001
	if opts.get("debug_buttons", false):
		# calibration: every button's rectangle on top of everything
		var dq := MeshInstance3D.new()
		dq.mesh = _quad(w, h)
		var dm := StandardMaterial3D.new()
		dm.albedo_color = Color(1, 0, 1, 0.45)
		dm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		dm.no_depth_test = true
		dm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		dm.cull_mode = BaseMaterial3D.CULL_DISABLED
		dq.material_override = dm
		bn.add_child(dq)
	if visible:
		var q := MeshInstance3D.new()
		q.mesh = _prism("rect", w, h, 0.004, min(w, h) * 0.12)
		var m := _mat_color(Color(col.r, col.g, col.b, col.a), 0.8)
		q.material_override = m
		q.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		bn.add_child(q)
	if label != "" and fcol.a > 0.01 and float(b.get("font_size", 100)) > 0:
		var l := Label3D.new()
		l.text = label
		l.font_size = 64
		l.pixel_size = float(b.get("font_size", 100)) * TTS.BUTTON_UNIT * 0.75 / 64.0
		l.modulate = fcol
		l.outline_size = 0
		l.shaded = false
		l.double_sided = false
		l.rotation = Vector3(-PI / 2, 0, 0)
		l.position = Vector3(0, 0.004, 0)
		l.width = 2000
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		l.render_priority = 2
		bn.add_child(l)
	# its world corners, for the per-shot button report
	var corners := []
	for c in [Vector3(-w / 2, 0, -h / 2), Vector3(w / 2, 0, -h / 2), Vector3(w / 2, 0, h / 2), Vector3(-w / 2, 0, h / 2)]:
		corners.append(node.transform * bn.transform * c)
	var top: Vector3 = node.transform * bn.transform * Vector3.ZERO
	button_nodes.append({"guid": o.get("guid", ""), "kind": "input" if is_input else "button",
		"index": int(b.get("index", 0)), "label": label, "visible": visible, "corners": corners, "top_y": top.y})
