## Runtime Wavefront OBJ reader: v / vt / vn / f (polygons fan-triangulated,
## negative indices, missing uv/normal). OBJ is right-handed with CCW faces;
## TTS (Unity) mirrors x on import, and this renderer maps TTS space to Godot
## by mirroring x as well, so OBJ coordinates are used as-is in Godot's local
## space. Godot's front faces are clockwise: each triangle is reversed.
## Every "g"/"o"/"usemtl" group becomes its own surface (asset bundles give
## one material per sub-mesh; plain OBJs usually have one group).


static func load_obj(path: String, split_groups: bool = false) -> ArrayMesh:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return null
	var text := f.get_as_text()
	f.close()
	var pos := PackedVector3Array()
	var uvs := PackedVector2Array()
	var nrm := PackedVector3Array()
	var groups: Array = []          # Array of PackedInt32Array triples (v, vt, vn) per corner
	var cur := PackedInt32Array()
	var any_face_since_group := false
	for line in text.split("\n", false):
		if line.length() < 2:
			continue
		var c0 := line.unicode_at(0)
		var c1 := line.unicode_at(1)
		if c0 == 118:  # v
			var p := line.strip_edges().split(" ", false)
			if c1 == 32 or c1 == 9:
				if p.size() >= 4:
					pos.append(Vector3(p[1].to_float(), p[2].to_float(), p[3].to_float()))
			elif c1 == 116:  # vt
				if p.size() >= 3:
					uvs.append(Vector2(p[1].to_float(), 1.0 - p[2].to_float()))
				elif p.size() == 2:
					uvs.append(Vector2(p[1].to_float(), 1.0))
			elif c1 == 110:  # vn
				if p.size() >= 4:
					nrm.append(Vector3(p[1].to_float(), p[2].to_float(), p[3].to_float()))
		elif c0 == 102 and (c1 == 32 or c1 == 9):  # f
			var p := line.strip_edges().split(" ", false)
			var corners: Array = []
			for i in range(1, p.size()):
				var idx := p[i].split("/")
				var vi := idx[0].to_int()
				var ti := 0
				var ni := 0
				if idx.size() > 1 and idx[1] != "":
					ti = idx[1].to_int()
				if idx.size() > 2 and idx[2] != "":
					ni = idx[2].to_int()
				if vi < 0:
					vi = pos.size() + vi + 1
				if ti < 0:
					ti = uvs.size() + ti + 1
				if ni < 0:
					ni = nrm.size() + ni + 1
				corners.append(Vector3i(vi, ti, ni))
			for i in range(1, corners.size() - 1):
				# reversed (CCW -> Godot's CW front faces)
				for cc in [corners[0], corners[i + 1], corners[i]]:
					cur.append(cc.x)
					cur.append(cc.y)
					cur.append(cc.z)
			any_face_since_group = true
		elif split_groups and (line.begins_with("g ") or line.begins_with("usemtl ") or line.begins_with("o ")):
			if any_face_since_group:
				groups.append(cur)
				cur = PackedInt32Array()
				any_face_since_group = false
	if cur.size() > 0:
		groups.append(cur)
	var mesh := ArrayMesh.new()
	for g in groups:
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var has_n: bool = nrm.size() > 0
		var n: int = g.size() / 3
		var need_normals := false
		for k in range(n):
			var vi: int = g[k * 3]
			var ti: int = g[k * 3 + 1]
			var ni: int = g[k * 3 + 2]
			if ti > 0 and ti <= uvs.size():
				st.set_uv(uvs[ti - 1])
			else:
				st.set_uv(Vector2.ZERO)
			if has_n and ni > 0 and ni <= nrm.size():
				st.set_normal(nrm[ni - 1])
			else:
				need_normals = true
			if vi > 0 and vi <= pos.size():
				st.add_vertex(pos[vi - 1])
			else:
				st.add_vertex(Vector3.ZERO)
		if need_normals:
			st.generate_normals()
		st.generate_tangents()
		st.commit(mesh)
	return mesh
