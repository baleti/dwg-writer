"""Header handle variables (R2007+) vs AutoCAD dump.json header: chk_header_handles.py FILE STEM"""
import sys, json, dwgmodel
f, stem = sys.argv[1:3]
h = json.load(open('oracle-out/%s/dump.json' % stem))['header']
mh = dwgmodel.Model(open(f, 'rb').read()).header()
M = {'Clayer': 'CLAYER', 'Textstyle': 'TEXTSTYLE', 'Celtype': 'CELTYPE', 'Cmaterial': 'CMATERIAL', 'Dimstyle': 'DIMSTYLE', 'CmlstyleID': 'CMLSTYLE',
     'Dimtxsty': 'DIMTXSTY', 'Dimldrblk': 'DIMLDRBLK', 'Dimblk': 'DIMBLK', 'BlockTableId': 'BLOCK_CONTROL', 'LayerTableId': 'LAYER_CONTROL',
     'TextStyleTableId': 'STYLE_CONTROL', 'LinetypeTableId': 'LTYPE_CONTROL', 'ViewTableId': 'VIEW_CONTROL', 'UcsTableId': 'UCS_CONTROL',
     'ViewportTableId': 'VPORT_CONTROL', 'RegAppTableId': 'APPID_CONTROL', 'DimStyleTableId': 'DIMSTYLE_CONTROL', 'GroupDictionaryId': 'DICT_GROUP',
     'MLStyleDictionaryId': 'DICT_MLINESTYLE', 'NamedObjectsDictionaryId': 'DICT_NAMED_OBJECTS', 'LayoutDictionaryId': 'DICT_LAYOUTS',
     'PlotSettingsDictionaryId': 'DICT_PLOTSETTINGS', 'PlotStyleNameDictionaryId': 'DICT_PLOTSTYLES', 'MaterialDictionaryId': 'DICT_MATERIALS',
     'ColorDictionaryId': 'DICT_COLORS', 'VisualStyleDictionaryId': 'DICT_VISUALSTYLE', 'ByLayerLinetype': 'BYLAYER_LTYPE',
     'ByBlockLinetype': 'BYBLOCK_LTYPE', 'ContinuousLinetype': 'CONTINUOUS_LTYPE', 'Interfereobjvs': 'INTERFEREOBJVS', 'Interferevpvs': 'INTERFEREVPVS'}
ok = bad = 0; ex = []
for k, n in M.items():
    v = h.get(k)
    if not isinstance(v, dict): continue
    a = mh.get(n)
    if isinstance(a, tuple): a = a[1]
    if a is None and n.startswith('INTERFERE'): continue  # default objects are not stored
    if a == int(v['h'], 16): ok += 1
    else: bad += 1; ex.append((n, a, v['h']))
print(stem, 'equal', ok, 'differ', bad, ex[:8])
