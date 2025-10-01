# build_iah_el_premio_market_catalog.py
import pandas as pd, json, re, numpy as np
from difflib import SequenceMatcher
from collections import defaultdict
from pathlib import Path
import argparse

def load_csv(path):
    for enc in [None, "utf-8-sig", "latin-1"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise RuntimeError(f"Could not load {path}")

def norm(s): return re.sub(r'[^a-z0-9]+',' ',str(s).lower()).strip()
def match_ratio(a,b): return SequenceMatcher(None, norm(a), norm(b)).ratio()
def cg_label_to_name(label):
    if pd.isna(label): return None
    m = re.match(r'\s*CG\s*\d+\s*\*?(.*?)\*?$', str(label).strip())
    return m.group(1).strip().title() if m and m.group(1) else str(label).strip()

def to_py(v):
    if pd.isna(v): return None
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating,)): return float(v)
    return v

def json_safe(obj):
    if isinstance(obj, dict): return {k: json_safe(v) for k,v in obj.items()}
    if isinstance(obj, list): return [json_safe(x) for x in obj]
    return to_py(obj)

def main(data_dir, out_items_json, out_mods_json, out_map_csv, hierarchy_id=448, fuzzy_threshold=0.58):
    p = Path(data_dir)
    masters = load_csv(p/"MenuItemMasters(in).csv")
    classes = load_csv(p/"MenuItemClasses(in).csv")
    prices = load_csv(p/"MenuItemPrices(in).csv")
    definitions = load_csv(p/"MenuItemDefinitions(in).csv")
    hierarchy = load_csv(p/"Hierarchy(in).csv")

    classes_iah = classes[classes['HierarchyId']==hierarchy_id].copy()
    prices_iah = prices[prices['HierarchyId']==hierarchy_id].copy()
    defs_iah = definitions.merge(
        prices_iah[['MenuItemDefID']].drop_duplicates(),
        left_on='Id', right_on='MenuItemDefID', how='inner'
    ).drop(columns=['MenuItemDefID'])

    class_by_objectnum = classes_iah.set_index('ObjectNumber')
    class_rows = classes_iah[['ObjectNumber','Name']].dropna()

    def parse_cg(s):
        m = re.match(r'\s*CG\s*(\d+)', str(s)) if not pd.isna(s) else None
        return int(m.group(1)) if m else None
    definitions = definitions.copy()
    definitions['CG_Number'] = definitions['FirstName'].apply(parse_cg)
    cg_rows = definitions[definitions['CG_Number'].notna()][['Id','FirstName','CG_Number']].sort_values('CG_Number')

    cg_by_class_obj = defaultdict(set)
    for _, cg in cg_rows.iterrows():
        for _, prow in class_rows.iterrows():
            if match_ratio(prow['Name'], cg['FirstName']) >= fuzzy_threshold:
                cg_by_class_obj[int(prow['ObjectNumber'])].add(int(cg['CG_Number']))

    mods_by_group = defaultdict(list)
    for _, d in definitions.iterrows():
        if not pd.isna(d.get('MenuItemClass')):
            mic = int(d['MenuItemClass'])
            if 90000 <= mic < 100000 and not str(d['FirstName']).strip().upper().startswith("CG "):
                group_num = mic - 90000
                mods_by_group[group_num].append({
                    "id": int(d['Id']),
                    "name": str(d['FirstName']).strip(),
                    "menu_item_class": mic
                })

    price_rows_by_def = prices_iah.groupby('MenuItemDefID')
    def prices_for_def(def_id):
        rows = price_rows_by_def.get_group(def_id) if def_id in price_rows_by_def.groups else pd.DataFrame(columns=prices_iah.columns)
        out = []
        for _, r in rows.iterrows():
            out.append({
                "price": to_py(r['Price']),
                "menu_level": to_py(r['MenuLevel']),
                "price_sequence": to_py(r['PriceSequence']),
                "tax_class": to_py(r['TaxClass'])
            })
        seen, uniq = set(), []
        for p in out:
            key = (p['price'], p['menu_level'], p['price_sequence'], p['tax_class'])
            if key not in seen:
                seen.add(key); uniq.append(p)
        return uniq

    masters_lookup = masters.set_index('Id')[['MajorGroup','FamilyGroup','MasterName','MenuItemName']]
    def enrich_with_master(entry, def_row):
        mid = to_py(def_row['MenuItemMasterId'])
        if mid and mid in masters_lookup.index:
            m = masters_lookup.loc[mid]
            entry['major_group'] = to_py(m['MajorGroup'])
            entry['family_group'] = to_py(m['FamilyGroup'])
            entry['master_name'] = to_py(m['MasterName'])
            entry['menu_item_name'] = to_py(m['MenuItemName'])
        else:
            entry['major_group'] = entry['family_group'] = entry['master_name'] = entry['menu_item_name'] = None
        return entry

    parents, modifiers_inventory = [], []
    for _, d in defs_iah.iterrows():
        nm = str(d['FirstName']).strip()
        if nm.upper().startswith("CG "): continue
        mic = to_py(d['MenuItemClass'])
        def_id = int(d['Id'])

        if mic is None: continue
        if mic >= 90000:
            modifiers_inventory.append({"id": def_id, "name": nm, "menu_item_class": mic, "prices": prices_for_def(def_id)})
            continue
        if mic not in class_by_objectnum.index: continue

        cls = class_by_objectnum.loc[mic]
        cg_nums = sorted(list(cg_by_class_obj.get(mic, [])))
        groups = []
        for g in cg_nums:
            heading = cg_rows[cg_rows['CG_Number']==g]['FirstName']
            group_name = cg_label_to_name(heading.iloc[0]) if not heading.empty else f"Group {g}"
            items = mods_by_group.get(g, [])
            items_w_price = [{**it, "prices": prices_for_def(it['id'])} for it in items]
            groups.append({"cg_number": g, "group_name": group_name, "modifiers": items_w_price})

        entry = {
            "id": def_id,
            "name": nm,
            "menu_item_class": mic,
            "class_name": to_py(cls['Name']),
            "tax_class": to_py(cls['TaxClass']),
            "sales_itemizer": to_py(cls['SalesItemizer']),
            "discount_itemizer": to_py(cls['DiscountItemizer']),
            "prices": prices_for_def(def_id),
            "modifier_groups": groups
        }
        parents.append(json_safe(enrich_with_master(entry, d)))

    with open(out_items_json, "w") as f: json.dump(parents, f, indent=2)
    with open(out_mods_json, "w") as f: json.dump(json_safe(modifiers_inventory), f, indent=2)
    mapping_rows = [{"class_object_number": c, "class_name": to_py(class_by_objectnum.loc[c]['Name']),
                     "cg_numbers": ",".join(map(str, sorted(gs)))} for c, gs in cg_by_class_obj.items()]
    pd.DataFrame(mapping_rows).sort_values("class_name").to_csv(out_map_csv, index=False)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data_dir", default="")
    ap.add_argument("--out_items_json", default="processed/iah_el_premio_market_items_with_mods.json")
    ap.add_argument("--out_mods_json", default="processed/iah_el_premio_market_modifiers.json")
    ap.add_argument("--out_map_csv", default="processed/iah_el_premio_market_class_to_cg_map.csv")
    ap.add_argument("--hierarchy_id", type=int, default=448)
    ap.add_argument("--fuzzy_threshold", type=float, default=0.58)
    args = ap.parse_args()
    main(**vars(args))
