

def sort_categories(categories: list[dict]) -> list[dict]:
    sorted_cats = []
    roots = [c for c in categories if not c.get("parent")]
    for root in roots:
        sorted_cats.append(root)
        root_id = root.get("idnumber") or root["name"]
        hijos_n1 = [c for c in categories if c.get("parent") == root_id]
        for h1 in hijos_n1:
            sorted_cats.append(h1)
            h1_id = h1.get("idnumber") or h1["name"]
            hijos_n2 = [c for c in categories if c.get("parent") == h1_id]
            for h2 in hijos_n2:
                sorted_cats.append(h2)
                h2_id = h2.get("idnumber") or h2["name"]
                hijos_n3 = [c for c in categories if c.get("parent") == h2_id]
                sorted_cats.extend(hijos_n3)
    orphans = [c for c in categories if c not in sorted_cats]
    sorted_cats.extend(orphans)
    return sorted_cats
