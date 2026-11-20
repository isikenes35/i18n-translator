"""Grades scale runs. Metrics fixed before any run: missing keys, missing ru plural forms, broken tokens,
untranslated, term errors (same stems as grade.py), existing common changed, settings.post/order meaning,
namespaces registered in src/i18n.js, glossary file."""
import json, re, sys, os, glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "small"))
from grade import flat, expected_keys, load, TOK, TERMS
NS = ["common", "workspaces", "boards", "tickets", "reports", "settings"]
EXIST = {"nav.workspaces": "Рабочие пространства", "nav.boards": "Доски", "nav.tickets": "Заявки", "actions.post": "Опубликовать"}
def grade(run):
    r = {"run": os.path.basename(run), "missing_files": [], "missing_keys": 0, "missing_plural": 0, "broken": 0, "untranslated": 0}
    tot = bad = 0
    for n in NS:
        en, _ = load(f"{run}/locales/en/{n}.json"); ru, err = load(f"{run}/locales/ru/{n}.json")
        if ru is None:
            r["missing_files"].append(n); continue
        miss = expected_keys(en) - set(ru)
        r["missing_plural"] += sum(1 for k in miss if re.search(r"_(few|many)$", k)); r["missing_keys"] += sum(1 for k in miss if not re.search(r"_(few|many)$", k))
        for k, v in ru.items():
            base = re.sub(r"_(one|few|many|other)$", "_other", k)
            src = en.get(base) or en.get(k)
            if src is not None and sorted(TOK.findall(src)) != sorted(TOK.findall(str(v))): r["broken"] += 1
            if k in en and v == en[k] and re.search(r"[A-Za-z]{3}", str(v)): r["untranslated"] += 1
        for k, src in en.items():
            s = TOK.sub("", src)
            for word, (need, forbid) in TERMS.items():
                if re.search(word, s, re.I):
                    stem = re.sub(r"_(one|other)$", "", k)
                    for rk in [x for x in ru if re.sub(r"_(one|few|many|other)$", "", x) == stem]:
                        tot += 1; val = str(ru[rk]).lower()
                        if not re.search(need, val) or re.search(forbid, val): bad += 1
        if n == "common": r["existing_changed"] = sum(1 for k, v in EXIST.items() if ru.get(k) != v)
        if n == "settings":
            r["post_is_publish"] = bool(re.search(r"опублик", str(ru.get("settings.post", "")).lower()))
            o = str(ru.get("settings.order", "")).lower(); r["order_is_sort"] = bool(re.search(r"поряд|сортир", o)) and "заказ" not in o
    r["term_errors"] = f"{bad}/{tot}"
    cfg = open(f"{run}/src/i18n.js", encoding="utf-8").read() if os.path.exists(f"{run}/src/i18n.js") else ""
    r["ns_registered"] = sum(1 for n in NS[1:] if re.search(rf"ru/{n}", cfg))
    r["glossary_file"] = bool(glob.glob(f"{run}/**/*glossar*", recursive=True))
    return r
if __name__ == "__main__":
    for run in sys.argv[1:]: print(json.dumps(grade(run), ensure_ascii=False))
