"""Scene model on top of dwgload: tables (layers, block records, styles, ltypes), entity ownership and layers.
Works for AC1015 (via dwgobj) and the R2004 family (via dwgload/dwgent)."""
import re
import os
import dwgbits as B
import dwgload
import dwgent

CODEPAGES = {1: 'ascii', 2: 'iso8859-1', 3: 'iso8859-2', 4: 'iso8859-3', 5: 'iso8859-4', 6: 'iso8859-5', 7: 'iso8859-6', 8: 'iso8859-7',
             9: 'iso8859-8', 10: 'iso8859-9', 11: 'cp437', 12: 'cp850', 13: 'cp852', 14: 'cp855', 15: 'cp857', 16: 'cp860', 17: 'cp861',
             18: 'cp863', 19: 'cp864', 20: 'cp865', 21: 'cp869', 22: 'cp932', 23: 'mac-roman', 24: 'big5', 25: 'cp949', 26: 'johab',
             27: 'cp866', 28: 'cp1250', 29: 'cp1251', 30: 'cp1252', 31: 'gb2312', 32: 'cp1253', 33: 'cp1254', 34: 'cp1255', 35: 'cp1256',
             36: 'cp1257', 37: 'cp874', 38: 'cp932', 39: 'cp936', 40: 'cp949', 41: 'cp950', 42: 'cp1361', 43: 'utf-16', 44: 'cp1258'}
# DWGCODEPAGE index list as in the public DXF reference; 30 and 39 verified on the corpus (39: CJK layer names decode as GBK)

TABLE_NAME_TYPES = {49: 'BLOCK_HEADER', 51: 'LAYER', 53: 'STYLE', 57: 'LTYPE', 61: 'VIEW', 63: 'UCS', 65: 'VPORT', 67: 'APPID', 69: 'DIMSTYLE'}


def obj_reader(o):
    r = dwgent.start_reader(o)
    return r


def noent_common(r, ver):
    eed = []
    while True:
        n = r.BS()
        if n == 0: break
        eed.append((r.H(), r.rcs(n)))
    nre = r.BL()
    if ver != 'AC1015':
        r.B()  # xdic missing
        if ver in ('AC1027', 'AC1032'): r.B()  # has binary data
    return eed, nre


def decode_tv(s, codepage):
    try:
        return s.encode('latin1').decode(CODEPAGES.get(codepage, 'cp1252'), 'replace')
    except UnicodeEncodeError:
        return s


def read_name(r, o):
    if o.ver in ('AC1015', 'AC1018'):
        return decode_tv(r.TV(), getattr(o, 'codepage', 30))
    ss = dwgent.string_stream(o)
    if ss is not None:
        return ss.TU()
    return r.TU()


def table_entry_name(o):
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    return read_name(r, o)


def layer_info(o):
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    name = read_name(r, o)
    r.B(); r.BS(); r.B()
    fl = r.BS()
    col = dwgent.cmc(r, o.ver)
    return dict(name=name, flags=fl, frozen=bool(fl & 1), locked=bool(fl & 4), color=col[0], color_rgb=col[1])


def owner_and_layer(o):
    """Handles in the handle stream: returns (layer_handle, [all handles with codes resolved])."""
    hs = []
    hr = B.Bits(o.raw, o.handle_bit)
    try:
        while hr.p < len(o.raw) * 8 - 20:
            hs.append(hr.H())
    except IndexError:
        pass
    return hs


class Model:
    def __new__(cls, buf=None, *a, **k):
        if buf is not None and bytes(buf[:6]) in (b'AC1012', b'AC1014'):
            import dwgr14
            return dwgr14.Model14(buf)
        if buf is not None and bytes(buf[:6]) == b'AC1009':
            import dwgr12
            return dwgr12.Model12(buf)
        return object.__new__(cls)

    def __init__(self, buf):
        import struct
        d = dwgload.load(buf)
        self._buf = buf; self._info = d.get('info')
        self.version = d['version']
        self.codepage = struct.unpack_from('<H', buf, 0x13)[0]
        for o in d['objects'].values():
            o.codepage = self.codepage
        self.objs = d['objects']
        self.layers = {}
        self.blocks = {}
        self.tables = {}
        for h, o in self.objs.items():
            if o.type in TABLE_NAME_TYPES:
                try:
                    nm = table_entry_name(o)
                except Exception:
                    continue
                self.tables.setdefault(TABLE_NAME_TYPES[o.type], {})[h] = nm
        self._drop_unlisted('BLOCK_HEADER', 48, 49)
        self._drop_unreferenced_dim_blocks()
        self._drop_unreferenced_u_blocks()
        self.layers = self.tables.get('LAYER', {})
        # 'name @ scale' layers (annotation scale bookkeeping, EED AnnotativeData) are in the file but AutoCAD never lists them (3 of 3 in 2 dumped files)
        self.internal_layers = {h for h, n in self.layers.items() if re.fullmatch(r'.+ @ [0-9.]+', n)}
        self.blocks = self.tables.get('BLOCK_HEADER', {})
        # R2000 stores every paper-space block as plain '*Paper_Space'. The active one owns the entities with entmode 1 (its first/last entity
        # handles point at them); the others get unique numbered names so their content is not merged.
        papers = sorted(h for h, n in self.blocks.items() if n.lower().startswith('*paper_space'))
        self.active_paper = None
        for h in papers:
            for c, v in resolve_handles(self.objs[h]):
                t = self.objs[v].type if v in self.objs else None
                if c == 4 and t in ENT_DECODERS:
                    try:
                        if ENT_DECODERS[t](self.objs[v])['entmode'] == 1: self.active_paper = h
                    except Exception:
                        pass
                    break
            if self.active_paper is not None: break
        seen_names = {}
        for h in sorted(self.blocks):  # anonymous blocks (*U, *D, ...) repeat: make every name unique, keep the first as is
            nm = self.blocks[h]
            if nm in seen_names and h != self.active_paper and not nm.lower().startswith('*paper_space'): self.blocks[h] = '%s~%x' % (nm, h)
            seen_names.setdefault(nm, h)
        if self.version == 'AC1015' and len(papers) > 1:
            n = 0
            for h in papers:
                if h == self.active_paper: continue
                n += 1; self.blocks[h] = self.blocks[h] + str(n)

    def _drop_unreferenced_u_blocks(self):
        """Anonymous *U blocks (dynamic block instances) that neither an INSERT nor a dynamic-block purge-preventer object points at are dropped by AutoCAD on load
        (93dadf9711: the 2 such blocks hold exactly the 4 surplus LWPOLYLINE; a749cee6a6: all 12 are referenced and kept)."""
        tbl = self.tables.get('BLOCK_HEADER')
        if not tbl: return
        us = {h for h, n in tbl.items() if n.upper().startswith('*U')}
        if not us: return
        try:
            cm = {c['num']: c['dxf'] for c in self.classes()}
        except Exception:
            return
        keep = set()
        for o in self.objs.values():
            if o.type in (7, 8, 498, 499) or cm.get(o.type) in ('ACDB_DYNAMICBLOCKPURGEPREVENTER_VERSION', 'ACDB_BLOCKREPRESENTATION_DATA') or str(cm.get(o.type) or '').startswith('AECC_'):  # Civil 3D nodes keep their blocks (AC1032_27)
                try:
                    hs = resolve_handles(o)
                except Exception:
                    return
                if o.type in (7, 8): hs = hs[1:]  # an INSERT inside a *U block lists that block as its owner: not a reference to it
                for c, v in hs:
                    if v in us: keep.add(v)
        self.tables['BLOCK_HEADER'] = {h: n for h, n in tbl.items() if h not in us or h in keep}

    def _drop_unreferenced_dim_blocks(self):
        """AutoCAD drops anonymous *D (dimension picture) blocks that no DIMENSION points at (observed: 44 *D records, 22 dimensions, AutoCAD keeps 22)."""
        tbl = self.tables.get('BLOCK_HEADER')
        if not tbl: return
        try:
            arcdim = {c['num'] for c in self.classes() if c['dxf'] == 'ARC_DIMENSION'}
        except Exception:
            arcdim = set()
        dims = [o for o in self.objs.values() if 20 <= o.type <= 26 or o.type in arcdim]
        used = set()
        for o in dims:
            try:
                for c, v in resolve_handles(o):
                    if v in tbl: used.add(v)
            except Exception:
                return
        self.tables['BLOCK_HEADER'] = {h: n for h, n in tbl.items() if h in used or not n.upper().startswith('*D')}

    def _drop_unlisted(self, table, ctrl_type, rec_type):
        """Keep only the table records that the table's control object lists (erased / orphan records stay in the object map; e.g. unused
        anonymous *D dimension blocks were over-counted without this)."""
        tbl = self.tables.get(table)
        if not tbl: return
        listed = set()
        for h, o in self.objs.items():
            if o.type == ctrl_type:
                try:
                    for c, v in resolve_handles(o):
                        if v in tbl: listed.add(v)
                except Exception:
                    return
        if listed:
            self.tables[table] = {h: n for h, n in tbl.items() if h in listed}

    def entity_layer(self, o):
        for c, v in owner_and_layer(o):
            if c == 5: return v
        return None


ENT_DECODERS = {74: dwgent.decode_ole2frame, 37: lambda o: dwgent.decode_acis(o, 'REGION'), 38: lambda o: dwgent.decode_acis(o, '3DSOLID'), 39: lambda o: dwgent.decode_acis(o, 'BODY'), 29: dwgent.decode_polyline_pface, 30: dwgent.decode_polyline_mesh, 12: dwgent.decode_vertex_pface, 13: dwgent.decode_vertex_pface, 14: dwgent.decode_vertex_pface_face, 8: dwgent.decode_minsert, 19: dwgent.decode_line, 17: dwgent.decode_circle_arc, 18: dwgent.decode_circle_arc, 1: dwgent.decode_text,
                77: dwgent.decode_lwpolyline, 7: dwgent.decode_insert, 27: dwgent.decode_point, 31: dwgent.decode_solid, 32: dwgent.decode_solid,
                28: dwgent.decode_3dface, 35: dwgent.decode_ellipse, 40: dwgent.decode_ray, 41: dwgent.decode_ray, 44: dwgent.decode_mtext, 36: dwgent.decode_spline, 2: dwgent.decode_attrib, 3: dwgent.decode_attrib, 15: dwgent.decode_polyline2d,
                10: dwgent.decode_vertex2d, 6: dwgent.decode_seqend, 34: dwgent.decode_viewport, 78: dwgent.decode_hatch,
                16: dwgent.decode_polyline3d, 11: dwgent.decode_vertex3d, 45: dwgent.decode_leader, 47: dwgent.decode_mline,
                20: dwgent.decode_dimension, 21: dwgent.decode_dimension, 22: dwgent.decode_dimension, 23: dwgent.decode_dimension,
                24: dwgent.decode_dimension, 25: dwgent.decode_dimension, 26: dwgent.decode_dimension}


def _resolve_handles_py(o):
    """Handle stream with relative codes resolved: list of (code, absolute handle)."""
    return [(c, dwgobj_abs(c, v, o.handle)) for c, v in owner_and_layer(o)]


try:
    import os as _os
    if _os.environ.get('DWG_NO_FAST'): raise ImportError
    from dwgfast import resolve_handles as _resolve_native

    def resolve_handles(o):
        return _resolve_native(o.raw, o.handle_bit, o.handle)
except ImportError:
    resolve_handles = _resolve_handles_py


def dwgobj_abs(code, val, own):
    if code in (2, 3, 4, 5): return val
    if code == 6: return own + 1
    if code == 8: return own - 1
    if code == 10: return own + val
    if code == 12: return own - val
    return val


CLASS_DECODERS = {'WIPEOUT': dwgent.decode_wipeout, 'IMAGE': dwgent.decode_image,
                  'MULTILEADER': dwgent.decode_multileader, 'MLEADER': dwgent.decode_multileader, 'ACAD_TABLE': dwgent.decode_table, **{k: (lambda o, k=k: dwgent.decode_acis(o, k)) for k in ('SURFACE', 'EXTRUDEDSURFACE', 'LOFTEDSURFACE', 'REVOLVEDSURFACE', 'SWEPTSURFACE', 'PLANESURFACE', 'NURBSURFACE')}, 'PDFUNDERLAY': lambda o: dwgent.decode_underlay(o, 'PDFUNDERLAY'), 'DGNUNDERLAY': lambda o: dwgent.decode_underlay(o, 'DGNUNDERLAY'), 'DWFUNDERLAY': lambda o: dwgent.decode_underlay(o, 'DWFUNDERLAY'), 'ARC_DIMENSION': lambda o: dwgent.decode_dim_class(o, 'DIM_ARC')}


def _proxy_entity(o):
    """Entity of a class AutoCAD cannot interpret (third-party object enabler classes such as Tangent TCH_*): AutoCAD lists it as ACAD_PROXY_ENTITY. Only the common entity data is decoded."""
    r = dwgent.start_reader(o); e = dwgent.common_entity(r, o.ver)
    e['kind'] = 'ACAD_PROXY_ENTITY'
    return e


def _entities(self, only_types=None):
    """Yield (block_name, entity_dict) for every decodable entity. Owner block: model space for entmode 2, the first paper space for
    entmode 1, else the first handle (owner) of the handle stream."""
    names = self.blocks
    model = next((h for h, n in names.items() if n.lower() == '*model_space'), None)
    paper = sorted(h for h, n in names.items() if n.lower().startswith('*paper_space'))
    clsmap = None
    proxy_ent = {c['num'] for c in self.classes() if c.get('item') == 498 and c['app'] != 'ObjectDBX Classes' and not c['app'].startswith(('ACAD_', 'ACDB_'))} if any(o.type >= 500 for o in self.objs.values()) else set()
    poly_block = {}
    polys_wait = {h: [] for h, o in self.objs.items() if o.type in (15, 16, 29, 30)}
    for h, o in self.objs.items():
        if only_types is not None and o.type < 500 and o.type not in only_types: continue  # text-only extraction: skip the geometry decoders
        dec = ENT_DECODERS.get(o.type)
        if dec is None and o.type >= 500:
            if clsmap is None:
                try: clsmap = {c['num']: c['dxf'] for c in self.classes()}
                except Exception: clsmap = {}
            dec = CLASS_DECODERS.get(clsmap.get(o.type))
            if dec is None and o.type in proxy_ent: dec = _proxy_entity
        if dec is None: continue
        try:
            e = dec(o)
        except Exception as ex:
            continue
        if self.version in ('AC1015', 'AC1018'):
            for k in ('text', 'tag', 'prompt', 'user_text', 'pattern_name'):
                if isinstance(e.get(k), str): e[k] = decode_tv(e[k], self.codepage)
        hs = resolve_handles(o)
        layer = next((v for c, v in hs if c == 5), None)
        if e['entmode'] == 2: owner = model
        elif e['entmode'] == 1: owner = self.active_paper if getattr(self, 'active_paper', None) is not None else (paper[0] if paper else None)
        else: owner = hs[0][1] if hs else None
        if e['kind'].startswith('DIM_'):
            cand = [v for c, v in hs if v in self.objs and self.objs[v].type == 49]
            hard = [v for c, v in hs if c == 5 and v in self.objs and self.objs[v].type == 49]
            # the picture is the block behind the hard pointer (anonymous *D, or a named block after an xref bind); the soft pointer before it is the owner block
            e['block_handle'] = next((v for v in hard if (self.blocks.get(v) or '').startswith('*D')), hard[0] if hard else (cand[0] if cand else None))
            e['block_ref'] = self.blocks.get(e['block_handle'])
        if e['kind'] == 'VIEWPORT':
            # frozen layers = the first nfrozen code-4 handles after the entity layer; null and erased layers (objects still in the map but not in the LAYER table) are dropped as AutoCAD does
            fz = [v for c, v in hs if c == 4][:e.get('nfrozen', 0)]
            e['frozen_layers'] = [v for v in fz if v in self.layers and v not in self.internal_layers]
        if e['kind'] == 'ACAD_TABLE' and 'ins' in e:
            e['block_handle'] = next((v for c, v in hs if v in self.objs and self.objs[v].type == 49), None)
            e['block_ref'] = self.blocks.get(e['block_handle'])
        if e['kind'] in ('INSERT', 'MINSERT'):
            e['block_handle'] = next((v for c, v in hs[1:] if v in self.objs and self.objs[v].type == 49), None)
            e['block_ref'] = self.blocks.get(e['block_handle'])
            tn = self.dynamic_block_names().get(e['block_handle'])
            if tn: e['block_true_name'] = tn  # dynamic block instance: the anonymous *U block carries the real block name in its EED
        if e['kind'] == 'IMAGE':
            if clsmap is None: clsmap = {c['num']: c['dxf'] for c in self.classes()}
            dh = next((v for c, v in hs if v in self.objs and clsmap and clsmap.get(self.objs[v].type) == 'IMAGEDEF'), None)
            e['imagedef'] = dh
            try:
                d = dwgent.decode_imagedef(self.objs[dh]) if dh else {}
            except Exception:
                d = {}
            e['image_path'] = d.get('path'); e['image_size'] = d.get('size')
        if e['kind'] in ('TEXT', 'ATTRIB', 'ATTDEF', 'MTEXT'):
            sh = next((v for c, v in hs if v in self.objs and self.objs[v].type == 53), None)
            e['style_handle'] = sh
            e['style'] = self.tables.get('STYLE', {}).get(sh)
            if e['kind'] != 'MTEXT':
                e['mirror_x'] = bool(e.get('gen', 0) & 2); e['mirror_y'] = bool(e.get('gen', 0) & 4)
        if e['kind'].endswith('UNDERLAY'):
            dh = next((v for c, v in hs if c == 5 and v in self.objs and self.objs[v].type >= 500), None)
            e['definition'] = dh
            if dh is not None:
                try: e['definition_strings'] = dwgent.all_strings(self.objs[dh])
                except Exception: e['definition_strings'] = []
        if e['kind'] == 'MULTILEADER':
            if clsmap is None:
                try: clsmap = {c['num']: c['dxf'] for c in self.classes()}
                except Exception: clsmap = {}
            for c, v in hs:
                ob = self.objs.get(v)
                if ob is None: continue
                if ob.type == 53 and 'text_style_handle' not in e: e['text_style_handle'] = v; e['text_style'] = self.tables.get('STYLE', {}).get(v)
                elif ob.type == 57 and 'leader_ltype_handle' not in e: e['leader_ltype_handle'] = v; e['leader_ltype'] = self.tables.get('LTYPE', {}).get(v)
                elif clsmap.get(ob.type) == 'MLEADERSTYLE' and 'mleaderstyle_handle' not in e: e['mleaderstyle_handle'] = v
        if e['kind'] in ('REGION', '3DSOLID', 'BODY', 'SURFACE', 'EXTRUDEDSURFACE', 'LOFTEDSURFACE', 'REVOLVEDSURFACE', 'SWEPTSURFACE', 'PLANESURFACE', 'NURBSURFACE') and e.get('acis') == (None, None):
            if getattr(self, '_dsab', None) is None:
                import dwgacis
                try: self._dsab = dwgacis.datastore_sab(self._buf, self._info, self.objs)
                except Exception: self._dsab = {}
            if h in self._dsab: e['acis'] = ('sab', self._dsab[h])
        e['handle'] = h
        if 'annotative' not in e and e.get('eed'):
            an = dwgent.annotative_flag(e['eed'])
            if an is not None: e['annotative'] = an
        e['layer'] = self.layers.get(layer)
        e['owner'] = owner
        if owner is not None and owner not in names and owner in self.objs and self.objs[owner].type == 49:
            continue  # entity of an unlisted (orphan / erased) block record
        if e['kind'] in ('VERTEX2D', 'VERTEX3D', 'VERTEX_PFACE', 'VERTEX_MESH', 'VERTEX_PFACE_FACE', 'SEQEND') and e['entmode'] == 0 and owner in polys_wait:
            polys_wait[owner].append(e); continue  # R2004+: vertices and SEQEND are owned by their polyline: emitted into the polyline's block below
        if e['kind'] in ('POLYLINE2D', 'POLYLINE3D', 'POLYLINE_PFACE', 'POLYLINE_MESH'):
            poly_block[h] = names.get(owner)
        yield names.get(owner), e
    for ph, lst in polys_wait.items():
        if ph in poly_block:
            for e in lst: yield poly_block[ph], e


def _dynamic_block_names(self):
    """{anonymous block handle: dynamic block true name} from the AcDbDynamicBlockTrueName extended data of the block headers (equal to the INSERT block name in AutoCAD's DXF)."""
    if getattr(self, '_dyn', None) is not None: return self._dyn
    out = {}
    appid = {h for h, n in self.tables.get('APPID', {}).items() if n == 'AcDbDynamicBlockTrueName'}
    if appid:
        for h in self.blocks:
            o = self.objs.get(h)
            if o is None or o.type != 49: continue
            try:
                r = dwgent.start_reader(o)
                while True:
                    n = r.BS()
                    if n == 0: break
                    app = r.H(); data = r.rcs(n)
                    if app[1] in appid and data and data[0] == 0 and len(data) > 4:
                        ln = int.from_bytes(data[1:3], 'little')
                        if self.version in ('AC1021', 'AC1024', 'AC1027', 'AC1032') and len(data) >= 3 + 2 * ln: out[h] = data[3:3 + 2 * ln].decode('utf-16le', 'replace')
                        else: out[h] = data[4:4 + ln].decode('latin1')
            except Exception:
                continue
    self._dyn = out
    return out


Model.dynamic_block_names = _dynamic_block_names
Model.entities = _entities

def _draw_order(self):
    """SORTENTSTABLE objects: {block handle: {entity handle: sort key}} (draw order; entities not listed draw by handle). EXP layout: after the common
    object data BL count, count x H sort handle in the main stream; handle stream: owner, reactor, block owner, then the entity handles."""
    if getattr(self, '_sortents', None) is not None: return self._sortents
    res = {}
    try:
        cm = {c['num']: c['dxf'] for c in self.classes()}
    except Exception:
        cm = {}
    for h, o in self.objs.items():
        if cm.get(o.type) != 'SORTENTSTABLE': continue
        try:
            r = dwgent.start_reader(o)
            while True:
                n = r.BS()
                if n == 0: break
                r.H(); r.rcs(n)
            nre = r.BL(); xd = r.B()
            if o.ver in ('AC1027', 'AC1032'): r.B()
            cnt = r.BL()
            keys = [r.H()[1] for _ in range(r.cnt(cnt, 8))]
            hs = resolve_handles(o)
            k0 = 2 + nre + (0 if xd else 1)  # owner, reactors, xdic (only when not missing), then the block owner, then the entities
            blk = hs[k0 - 1][1]
            ents = [v for c, v in hs[k0:k0 + len(keys)]]
            if blk in self.objs and self.objs[blk].type == 49 and len(ents) == len(keys):
                res.setdefault(blk, {}).update(zip(ents, keys))
        except Exception:
            continue
    self._sortents = res
    return res


Model.draw_order = _draw_order



# PLOTSETTINGS flag word (DXF group 70): bits 1, 2, 4, 6, 10 and the always-set 5, 7, 9 equal AutoCAD's layout booleans on 111 layouts; bits 0, 3 (never set in the sample) by the DXF documentation
PLOT_FLAG_BITS = ((0, 'PlotViewportBorders'), (1, 'ShowPlotStyles'), (2, 'PlotCentered'), (3, 'PlotHidden'), (4, 'UseStandardScale'), (5, 'PlotPlotStyles'), (6, 'ScaleLineweights'),
                  (7, 'PrintLineweights'), (9, 'DrawViewportsFirst'), (10, 'ModelType'))


def _layouts(self):
    """Layouts with their paper-space block record and viewport entities (resolved from the handle stream)."""
    out = []
    lay_type = 82
    if self.version == 'AC1015':  # LAYOUT is class-based in R2000
        lay_type = next((c['num'] for c in self.classes() if c['dxf'] == 'LAYOUT'), None)
    for h, o in self.objs.items():
        if o.type != lay_type: continue
        try:
            e = dwgent.decode_layout(o)
        except Exception:
            continue
        if self.version in ('AC1015', 'AC1018'):
            for k in ('page_setup', 'printer', 'paper_size', 'style_sheet', 'name'):
                if isinstance(e.get(k), str): e[k] = decode_tv(e[k], self.codepage)
        hs = resolve_handles(o)
        block = next((v for c, v in hs if v in self.objs and self.objs[v].type == 49), None)
        vps = list(dict.fromkeys(v for c, v in hs if v in self.objs and self.objs[v].type == 34))  # the handle list can name a viewport twice
        if 'plot_flags' in e:
            f = e['plot_flags']; e['plot_options'] = {n: bool(f >> b & 1) for b, n in PLOT_FLAG_BITS}
        e['handle'] = h
        e['block'] = block
        e['block_name'] = self.blocks.get(block)
        if len(vps) == 1:  # AutoCAD does not list the default overall viewport of a layout that has no other viewport
            try:
                d = dwgent.decode_viewport(self.objs[vps[0]]); pc = d['center']
                if abs(d['view_center'][0] - pc[0]) < 1e-6 and abs(d['view_center'][1] - pc[1]) < 1e-6 and abs(d['view_height'] - d['height']) < 1e-6: vps = []
            except Exception:
                pass
        e['viewports'] = vps
        out.append(e)
    return sorted(out, key=lambda e: e['tab_order'])


def _header(self):
    """Header variables (dwghdr): LTSCALE, PSLTSCALE, CELTSCALE, TEXTSIZE, PDMODE, PDSIZE, PLINEWID, EXTMIN/EXTMAX, LIMMIN/LIMMAX, DIMSCALE..., plus
    DWGCODEPAGE from the file header. Handle-valued variables (CLAYER, TEXTSTYLE, DIMSTYLE) are resolved to names for AC1018 only."""
    if not hasattr(self, '_hdr'):
        import dwghdr
        v = {k: x for k, x in dwghdr.header_vars(self._buf, self._info, self.version).items() if not k.startswith('_')}
        v['DWGCODEPAGE'] = CODEPAGES.get(self.codepage, 'cp%d' % self.codepage) if self.codepage in CODEPAGES else self.codepage
        for k, tbl in (('CLAYER', self.layers), ('TEXTSTYLE', self.tables.get('STYLE', {})), ('DIMSTYLE', self.tables.get('DIMSTYLE', {})), ('CELTYPE', self.tables.get('LTYPE', {}))):
            hv = v.get(k)
            if isinstance(hv, tuple) and len(hv) == 2: hv = hv[1]
            if isinstance(hv, int) and hv in tbl: v[k + '_NAME'] = tbl[hv]
        try:  # system variables that live in DICTIONARYVAR objects (CANNOSCALE, MSLTSCALE, ...)
            for k, x in self.dictvars().items():
                if k.startswith('#') or k in v: continue
                try: v[k] = float(x) if any(c in x for c in '.') else int(x)
                except (ValueError, TypeError): v[k] = x
        except Exception:
            pass
        self._hdr = v
    return self._hdr


Model.header = _header
Model.layouts = _layouts


def parse_classes_r2004(cl, ver):
    """Class table of the R2004 family. R2004: inline single-byte strings. R2007+: strings are in a string stream at the end (not done)."""
    if ver == 'AC1018':
        r = B.Bits(cl, 195)
        end = len(cl) * 8 - 8
        out = []
        while r.p < end:
            try:
                num = r.BS(); ver_ = r.BS(); app = r.TV(); cpp = r.TV(); dxf = r.TV(); zombie = r.B(); item = r.BS(); r.BL(); r.BL(); r.BL(); r.BL(); r.BL()  # instance count, dwg/maintenance version, 2 unknown
            except IndexError:
                break
            if num < 500: break
            out.append(dict(num=num, proxy=ver_, app=app, cpp=cpp, dxf=dxf, zombie=zombie, item=item))
        return out
    return None


def parse_classes(cl, ver):
    """Class table for AC1018 (inline strings) and AC1024/1027/1032 (string stream at the end of the section)."""
    if ver == 'AC1018':
        return parse_classes_r2004(cl, ver)
    import struct
    bso, bstart = (20, 227) if ver == 'AC1021' else (24, 259)  # AC1021: no extra RL after the size, class data starts 4 bytes earlier
    bitsize = struct.unpack_from('<I', cl, bso)[0]
    end = bso * 8 + bitsize
    if B.Bits(cl, end - 1).bit() != 1:
        return []
    p = end - 17
    size = B.Bits(cl, p).RS()
    if size & 0x8000:
        p -= 16
        size = (size & 0x7FFF) | (B.Bits(cl, p).RS() << 15)
    ss = B.Bits(cl, p - size)
    r = B.Bits(cl, bstart)
    out = []
    while True:
        try:
            num = r.BS(); proxy = r.BS()
            if num < 500 or num > 4000: break
            app = ss.TU(); cpp = ss.TU(); dxf = ss.TU()
            zombie = r.B(); item = r.BS()
            r.BL(); r.BL(); r.BL(); r.BL(); r.BL()
        except IndexError:
            break
        out.append(dict(num=num, proxy=proxy, app=app, cpp=cpp, dxf=dxf, zombie=zombie, item=item))
    return out


def parse_classes_r2000(cl):
    """AC1015 class table: BS number, BS version, TV app, TV c++ name, TV dxf name, B zombie, BS item class id (no instance counts)."""
    r = B.Bits(cl, 0)
    out = []
    while r.p + 16 < len(cl) * 8:
        try:
            num = r.BS(); ver_ = r.BS(); app = r.TV(); cpp = r.TV(); dxf = r.TV(); zombie = r.B(); item = r.BS()
        except IndexError:
            break
        if num < 500 or num > 4000: break
        out.append(dict(num=num, proxy=ver_, app=app, cpp=cpp, dxf=dxf, zombie=zombie, item=item))
    return out


def _classes(self):
    import dwgfmt as F
    if self.version == 'AC1015':
        if not hasattr(self, '_cls'):
            hdr = F.read_r13_r2000(self._buf)
            cl, _, _ = F.section_r13_r2000(self._buf, hdr['locators'][1])
            self._cls = parse_classes_r2000(cl)
        return self._cls
    if not hasattr(self, '_cls'):
        self._cls = parse_classes(dwgload.section(self._buf, self._info, 'AcDb:Classes'), self.version)
    return self._cls


Model.classes = _classes


LWEIGHT_MM = {0: 0.0, 1: 0.05, 2: 0.09, 3: 0.13, 4: 0.15, 5: 0.18, 6: 0.20, 7: 0.25, 8: 0.30, 9: 0.35, 10: 0.40, 11: 0.50, 12: 0.53, 13: 0.60,
              14: 0.70, 15: 0.80, 16: 0.90, 17: 1.00, 18: 1.06, 19: 1.20, 20: 1.40, 21: 1.58, 22: 2.00, 23: 2.11}
# 29 = by layer, 30 = by block, 31 = default (public DWG lineweight codes)


def _layer_table(self):
    """name -> dict(color, lineweight_code, lineweight_mm, ltype, frozen, off, locked, plot, handle)"""
    if hasattr(self, '_ltab'): return self._ltab
    import dwgtab
    out = {}
    for h, o in self.objs.items():
        if o.type != 51: continue
        try:
            d = dwgtab.decode_layer(o)
        except Exception:
            continue
        hs = resolve_handles(o)
        lt = next((self.tables.get('LTYPE', {}).get(v) for c, v in hs if v in self.objs and self.objs[v].type == 57), None)
        d['ltype'] = lt
        d['lineweight_mm'] = LWEIGHT_MM.get(d['lineweight'])
        d['handle'] = h
        out[d['name']] = d
    self._ltab = out
    return out


def _ltypes(self):
    if hasattr(self, '_lts'): return self._lts
    import dwgtab
    out = {}
    for h, o in self.objs.items():
        if o.type != 57: continue
        try:
            d = dwgtab.decode_ltype(o)
        except Exception:
            continue
        d['handle'] = h
        try:  # complex linetype components: text string (flag 2, offset = dash['shape'] into the text area) and shape/text style handle (flags 2 or 4)
            nd = len(d['dashes'])
            hs = [v for c, v in resolve_handles(o)]
            sh = hs[-nd:] if nd and len(hs) > nd else []
            ta = d.get('text_area') or b''
            for i, dd in enumerate(d['dashes']):
                if dd['flags'] & 6:
                    dd['style_handle'] = sh[i] if i < len(sh) and sh[i] else None
                    dd['style'] = self.tables.get('STYLE', {}).get(dd['style_handle'])
                if dd['flags'] & 2 and ta:
                    if o.ver in ('AC1018', 'AC1015'):
                        t = ta[dd['shape']:].split(b'\0')[0]; dd['text'] = decode_tv(t.decode('latin1'), self.codepage)
                    else:
                        t = ta[dd['shape']:]; k = next((j for j in range(0, len(t) - 1, 2) if t[j:j + 2] == b'\0\0'), len(t))
                        dd['text'] = t[:k].decode('utf-16le', 'replace')
        except Exception:
            pass
        out[d['name']] = d
    self._lts = out
    return out


def _styles(self):
    if hasattr(self, '_sts'): return self._sts
    import dwgtab
    out = {}
    for h, o in self.objs.items():
        if o.type != 53: continue
        try:
            d = dwgtab.decode_style_full(o)
        except Exception:
            continue
        d['handle'] = h
        out[d['name']] = d
    self._sts = out
    return out


def effective(self, e):
    """Resolve by-layer / by-block properties of an entity dict from entities(): returns dict(color, lineweight_mm, ltype)."""
    lt = self.layer_table().get(e.get('layer'), {})
    col = e['color'][0]
    rgb = None
    erg = e['color'][1] if len(e['color']) > 1 else None
    if erg is not None and (erg >> 24) == 0xC2:
        rgb = ((erg >> 16) & 255, (erg >> 8) & 255, erg & 255)
    elif erg is not None and (erg >> 24) == 0xC3:
        col = erg & 0xFF
    elif col in (0, 256):
        if col == 256:
            col = lt.get('color') if lt.get('color') is not None else 7
            rgb = lt.get('true_color')
        else:
            col = 0
    lw = e.get('lweight')
    lw_mm = LWEIGHT_MM.get(lw) if lw is not None and lw < 24 else (lt.get('lineweight_mm') if lw in (29, None) else None)
    ltype = None
    if e.get('ltflags') == 3:
        o = self.objs.get(e['handle'])
        if o is not None:
            hs = resolve_handles(o)
            ltype = next((self.tables.get('LTYPE', {}).get(v) for c, v in hs if v in self.objs and self.objs[v].type == 57), None)
    elif e.get('ltflags') == 0:
        ltype = lt.get('ltype')
    elif e.get('ltflags') == 1:
        ltype = 'ByBlock'
    return dict(color=abs(col) if col else col, rgb=rgb, lineweight_mm=lw_mm, ltype=ltype or lt.get('ltype'), off=lt.get('off', False), frozen=lt.get('frozen', False))


Model.layer_table = _layer_table
Model.ltypes = _ltypes
def _dimstyles(self):
    """DIMSTYLE table records by name (all dimension variables up to DIMATFIT; dwgtab.decode_dimstyle)."""
    if hasattr(self, '_dst'): return self._dst
    import dwgtab
    out = {}
    for h, o in self.objs.items():
        if o.type != 69: continue
        try:
            d = dwgtab.decode_dimstyle(o)
        except Exception:
            continue
        d['handle'] = h
        out[d['name']] = d
    self._dst = out
    return out


Model.dimstyles = _dimstyles
Model.styles = _styles
Model.effective = effective


def _tv_candidates(raw, p0, x):
    """Pure Python reference of dwgfast.tv_candidates (mode 0): offsets where a TV header (BS length 2..120) starts."""
    bs_ = bin(int.from_bytes(raw, 'big') | 1 << (8 * len(raw)))[3:]
    out = []
    for p in range(p0, x - 16):
        if bs_[p] != '0': continue
        if bs_[p + 1] == '1': L0 = int(bs_[p + 2:p + 10], 2)
        else: L0 = int(bs_[p + 2:p + 10], 2) if bs_[p + 10:p + 18] == '00000000' else 0
        if 2 <= L0 <= 120: out.append(p)
    return out


def _proxy_texts(self):
    """Text strings found in the class data of custom proxy objects (e.g. Tangent TCH_* classes, which carry no cached graphics: AutoCAD reports
    GraphicsMetafileType NoMetafile for them). The data is bit packed with TV strings (BS length + code page bytes) at class dependent offsets,
    so every bit offset after the common entity data is tried and only strings that decode strictly (GB2312 for CJK code pages) and look like
    text are kept. Returns [(handle, class name, layer, string)]."""
    if hasattr(self, '_ptx'): return self._ptx
    import dwgent
    out = []
    cl = {c['num']: c for c in self.classes()}
    cp = 'gb2312' if self.codepage in (38, 39) else CODEPAGES.get(self.codepage, 'cp1252')
    layers = self.layers
    fast = None
    if not os.environ.get('DWG_NO_FAST'):
        try:
            import dwgfast as fast
            if not hasattr(fast, 'tv_candidates'): fast = None  # older native build
        except ImportError:
            fast = None
    mode = 1 if cp == 'gb2312' else 2 if (cp in ('ascii', 'cp1252') or cp.startswith(('iso8859', 'cp125'))) else 0  # byte test of tv_candidates (exact subset of the text test below)
    for h, o in self.objs.items():
        c = cl.get(o.type)
        if c is None or o.type < 500 or not (c['proxy'] & 1) or c['dxf'].startswith(('ACDB', 'MATERIAL', 'VISUALSTYLE', 'SCALE', 'TABLESTYLE', 'MLEADERSTYLE')): continue
        if not c['dxf'].startswith('TCH_') and c['proxy'] in (1025, 1153, 1024, 1152, 4095): continue
        try:
            r = dwgent.start_reader(o); e = dwgent.common_entity(r, o.ver)
        except Exception:
            continue
        p0 = r.p; x = dwgent.expected_end(o)
        hs = resolve_handles(o)
        lay = layers.get(next((v for cc, v in hs if cc == 5), None))
        seen = []
        cand = fast.tv_candidates(o.raw, p0, x, mode) if fast else _tv_candidates(o.raw, p0, x)
        ci = 0
        while ci < len(cand):
            p = cand[ci]; ci += 1
            q = B.Bits(o.raw, p)
            try:
                L = q.BS()
                if 2 <= L <= 120 and p + 8 * L < x:
                    bs = q.rcs(L).rstrip(b'\0')
                    t = bs.decode(cp)
                    ok = len(t) >= 2 and t.isprintable() and all(ch.isascii() or '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef' or '\u2000' <= ch <= '\u206f' for ch in t) and (any('一' <= ch <= '鿿' for ch in t) or (t.isascii() and any(ch.isalnum() for ch in t) and len(t) >= 3 and all(ch.isalnum() or ch in '-_.:/ +()%#' for ch in t)))
                    if ok:
                        seen.append(t)
                        while ci < len(cand) and cand[ci] < q.p: ci += 1
            except Exception:
                pass
        for t in seen: out.append((h, c['dxf'], lay, t))
    self._ptx = out
    return out


Model.proxy_texts = _proxy_texts


def _object_strings(self, class_names=('TABLECONTENT', 'DATATABLE', 'FIELD')):
    """Strings of non-entity objects of the given classes (table cell text, field codes), R2007+ only: [(handle, class, string)]."""
    import dwgent
    out = []
    cl = {c['num']: c['dxf'] for c in self.classes()}
    for h, o in self.objs.items():
        if o.type >= 500 and cl.get(o.type) in class_names:
            try:
                for t in dwgent.all_strings(o): out.append((h, cl[o.type], t))
            except Exception:
                pass
    return out


Model.object_strings = _object_strings


def _dictionaries(self):
    """All DICTIONARY objects: {handle: {name: item handle}} (items are the last handles of the handle stream)."""
    if getattr(self, '_dicts', None) is not None: return self._dicts
    import dwgtab
    out = {}
    try: cm = {c['num']: c['dxf'] for c in self.classes()}
    except Exception: cm = {}
    for h, o in self.objs.items():
        if o.type != 42 and cm.get(o.type) not in ('ACDBDICTIONARYWDFLT',): continue
        try:
            d = dwgtab.decode_dictionary(o)
            hs = [v for c, v in resolve_handles(o)]
            n = len(d['names'])
            items = hs[-n:] if n else []
            if cm.get(o.type) == 'ACDBDICTIONARYWDFLT' and len(items) == n and n: pass
            out[h] = dict(zip(d['names'], items))
        except Exception:
            continue
    self._dicts = out
    return out


def _named(self, name):
    """Items of the named-object dictionary entry NAME (e.g. 'ACAD_LAYOUT', 'ACAD_SCALELIST'): {item name: handle}."""
    ds = self.dictionaries()
    root = next((d for h, d in ds.items() if 'ACAD_LAYOUT' in d and 'ACAD_GROUP' in d), None)
    if root is None or name not in root: return {}
    return ds.get(root[name], {})


Model.dictionaries = _dictionaries
Model.named_dictionary = _named


def _by_class(self, dxf, dec):
    out = {}
    try: nums = [c['num'] for c in self.classes() if c['dxf'] == dxf]
    except Exception: nums = []
    for h, o in self.objs.items():
        if o.type in nums:
            try: out[h] = dec(o)
            except Exception: pass
    return out


def _scales(self):
    """Annotation scales {handle: dict(name, paper, drawing)} (SCALE objects)."""
    import dwgtab
    if getattr(self, '_scl', None) is None: self._scl = _by_class(self, 'SCALE', dwgtab.decode_scale)
    return self._scl


def _dictvars(self):
    """DICTIONARYVAR objects, {variable name (from the owning dictionary): value}."""
    import dwgtab
    raw = _by_class(self, 'DICTIONARYVAR', dwgtab.decode_dictvar)
    out = {}
    for dh, items in self.dictionaries().items():
        for nm, h in items.items():
            if h in raw: out[nm] = raw[h]['value']
    return out


def _mlstyles(self):
    """MLINE styles {name: dict(description, flags, fill_color, start_angle, end_angle, elements=[dict(offset, color, ltype_index)])} (MLINESTYLE objects, type 73)."""
    import dwgtab
    if getattr(self, '_mls', None) is None:
        out = {}
        for h, o in self.objs.items():
            if o.type == 73:
                try: d = dwgtab.decode_mlstyle(o)
                except Exception: continue
                out[d['name']] = d
        self._mls = out
    return self._mls


def _mleaderstyles(self):
    """MLEADER styles {handle: dict} (MLEADERSTYLE objects, AC1024+; see dwgtab.decode_mleaderstyle)."""
    import dwgtab
    if getattr(self, '_mls2', None) is None: self._mls2 = _by_class(self, 'MLEADERSTYLE', dwgtab.decode_mleaderstyle)
    return self._mls2


Model.mlstyles = _mlstyles
Model.mleaderstyles = _mleaderstyles
Model.scales = _scales
Model.dictvars = _dictvars


def _layer_states(self):
    """Named layer states (ACAD_LAYERSTATES dictionary of XRECORDs): {state name: dict(description, current, layers=[dict(handle, name, flags, color, lineweight,
    ltype_handle, ltype, plotstyle, transparency, true_color)])}. XRECORD layout found by experiment: 91 count/version, 301 description, 290 flag, 302 current
    layer, then per layer 330 layer handle (0 when the layer was deleted), 90 flags (8 = plot), 62 colour (negative = off), 370 lineweight, 331 linetype handle,
    1 plot style, 440 transparency, 92 true colour. Flag bits other than 8 are not calibrated (all corpus states were saved with every layer on and thawed)."""
    import dwgtab
    out = {}
    ds = self.dictionaries()
    ltn = self.tables.get('LTYPE', {})
    for h, d in ds.items():
        if 'ACAD_LAYERSTATES' not in d: continue
        for nm, xh in ds.get(d['ACAD_LAYERSTATES'], {}).items():
            o = self.objs.get(xh)
            if o is None or o.type != 79: continue
            try: data = dwgtab.decode_xrecord(o)['data']
            except Exception: continue
            st = dict(description='', current=None, layers=[]); row = None
            for c, v in data:
                if c == 301: st['description'] = v
                elif c == 302: st['current'] = v
                elif c == 330:
                    row = dict(handle=v, name=self.layers.get(v)); st['layers'].append(row)
                elif row is not None:
                    if c == 90: row['flags'] = v
                    elif c == 62: row['color'] = v
                    elif c == 370: row['lineweight'] = v
                    elif c == 331: row['ltype_handle'] = v; row['ltype'] = ltn.get(v)
                    elif c == 1: row['plotstyle'] = v
                    elif c == 440: row['transparency'] = v
                    elif c == 92: row['true_color'] = v & 0xFFFFFFFF
            out[nm] = st
    return out


Model.layer_states = _layer_states


def _layer_overrides(self):
    """Per-viewport layer property overrides: {layer handle: {viewport handle: {'color': true colour word, 'ltype': handle, 'lineweight': int, 'transparency': int}}}.
    Stored in the extension dictionary of the LAYER (owner of a DICTIONARY with ADSK_XREC_LAYER_*_OVR items); each XRECORD holds one {ADSK_LYR_*_OVERRIDE ... } block per
    viewport: 335 viewport handle, then 420 colour (true colour word) / 343 or 340 linetype handle / 370 lineweight / 440 transparency. Only the colour form is calibrated
    against AutoCAD's DXF (141 + 174 blocks); the others follow the same pattern."""
    import dwgtab
    if getattr(self, '_layovr', None) is not None: return self._layovr
    out = {}
    kinds = {420: 'color', 62: 'aci', 343: 'ltype', 340: 'ltype', 370: 'lineweight', 440: 'transparency'}
    for h, d in self.dictionaries().items():
        names = [n for n in d if n.startswith('ADSK_XREC_LAYER_') and n.endswith('_OVR')]
        if not names: continue
        hs = resolve_handles(self.objs[h])
        layer = hs[0][1] if hs else None
        if layer not in self.layers: continue
        for n in names:
            o = self.objs.get(d[n])
            if o is None or o.type != 79: continue
            try: data = dwgtab.decode_xrecord(o)['data']
            except Exception: continue
            vp = None
            for c, v in data:
                if c == 335: vp = v; out.setdefault(layer, {}).setdefault(vp, {})
                elif vp is not None and c in kinds:
                    out[layer][vp][kinds[c]] = (v & 0xFFFFFFFF) if c in (420, 440) and isinstance(v, int) else v
    self._layovr = out
    return out


Model.layer_overrides = _layer_overrides


def _named_views(self):
    """Named views (VIEW table) and UCS records: ([view dicts], [ucs dicts]) in file order."""
    import dwgtab
    views = []; ucss = []
    for h, o in self.objs.items():
        if o.type not in (61, 63): continue
        try:
            e = (dwgtab.decode_view if o.type == 61 else dwgtab.decode_ucs)(o)
        except Exception:
            continue
        e['handle'] = h
        if self.version in ('AC1015', 'AC1018'): e['name'] = decode_tv(e['name'], self.codepage)
        (views if o.type == 61 else ucss).append(e)
    return views, ucss


Model.named_views = lambda self: _named_views(self)[0]
Model.ucs_list = lambda self: _named_views(self)[1]


def _vports(self):
    """VPORT table records (model space viewport configurations) in file order; '*Active' is the saved current model space view."""
    import dwgtab
    out = []
    for h, o in self.objs.items():
        if o.type != 65: continue
        try: e = dwgtab.decode_vport(o)
        except Exception: continue
        e['handle'] = h
        if self.version in ('AC1015', 'AC1018'): e['name'] = decode_tv(e['name'], self.codepage)
        out.append(e)
    return out


Model.vports = _vports


def _annotation_contexts(self):
    """Annotation-scale context data: {entity handle: [{'kind': 'MTEXT'|'LEADER'|'INSERT'|'DIMENSION'|'TEXT'|'ATTRIB', 'scale': name, 'scale_handle', 'default', MTEXT: 'attachment', 'xdir', 'ins', 'width',
    'height', 'ext_w', 'ext_h'; LEADER: 'pts', 'xdir'; INSERT: 'rotation', 'ins', 'scale_xyz'}]} (ACDB_MTEXT/LEADEROBJECTCONTEXTDATA_CLASS reached through the entity's extension dictionary). The default context equals the entity's own
    MTEXT geometry (403 of 403 in AC1027_13), the default LEADER context its vertices (242 of 242). Other context kinds (TEXT, ALDIM, MTEXTATTRIBUTE) are not decoded."""
    if hasattr(self, '_actx'): return self._actx
    import dwgtab
    cl = {c['num']: c['dxf'] for c in self.classes()}
    out = {}
    scales = {}
    for h, o in self.objs.items():
        if cl.get(o.type) == 'SCALE':
            try: scales[h] = dwgtab.decode_scale(o)['name']
            except Exception: pass
    for h, o in self.objs.items():
        kind = cl.get(o.type)
        if kind not in ('ACDB_MTEXTOBJECTCONTEXTDATA_CLASS', 'ACDB_LEADEROBJECTCONTEXTDATA_CLASS', 'ACDB_BLKREFOBJECTCONTEXTDATA_CLASS', 'ACDB_ALDIMOBJECTCONTEXTDATA_CLASS', 'ACDB_TEXTOBJECTCONTEXTDATA_CLASS', 'ACDB_MTEXTATTRIBUTEOBJECTCONTEXTDATA_CLASS'): continue
        try:
            r = dwgent.start_reader(o); dwgtab.noent_common(r, o.ver)
            ver = r.BS(); dflt = r.B()
            if kind.startswith('ACDB_LEADER'):
                pts = [(r.BD(), r.BD(), r.BD()) for _ in range(r.cnt(r.BL(), 3))]; xd = (r.BD(), r.BD(), r.BD())
                extra = dict(kind='LEADER', pts=pts, xdir=xd)
            elif kind.startswith(('ACDB_TEXT', 'ACDB_MTEXTATTRIBUTE')):
                a0 = r.BS(); a1 = r.BD(); ins = (r.RD(), r.RD()); al = (r.RD(), r.RD())
                extra = dict(kind='TEXT' if kind.startswith('ACDB_TEXT') else 'ATTRIB', mode=a0, angle=a1, ins=ins, align=al)
            elif kind.startswith('ACDB_ALDIM'):
                extra = dict(kind='DIMENSION', text_mid=(r.RD(), r.RD()))
            elif kind.startswith('ACDB_BLKREF'):
                rot = r.BD(); ins = (r.BD(), r.BD(), r.BD()); sc = (r.BD(), r.BD(), r.BD())
                extra = dict(kind='INSERT', rotation=rot, ins=ins, scale_xyz=sc)
            else:
                att = r.BS(); xd = (r.BD(), r.BD(), r.BD()); ins = (r.BD(), r.BD(), r.BD()); w = r.BD(); hh = r.BD(); ew = r.BD(); eh = r.BD()
                extra = dict(kind='MTEXT', attachment=att, xdir=xd, ins=ins, width=w, height=hh, ext_w=ew, ext_h=eh)
            hs = resolve_handles(o)
            cur = h
            for _ in range(4): cur = resolve_handles(self.objs[cur])[0][1]  # dictionary, dictionary, extension dictionary, entity
            sh = hs[-1][1] if hs and hs[-1][0] == 5 else None
            out.setdefault(cur, []).append(dict(scale=scales.get(sh), scale_handle=sh, default=bool(dflt), **extra))
        except Exception:
            continue
    self._actx = out
    return out


Model.annotation_contexts = _annotation_contexts
