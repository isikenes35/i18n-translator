"""Grades one or more run folders of the taskboard i18n test. Independent of the skill's own validator."""
import json, re, sys, os, glob

PLURAL_RU = ["one", "few", "many", "other"]
TOK = re.compile(r"\{\{\s*\w+\s*\}\}|<[^>]+>")
EXISTING = {"nav.workspaces": "Рабочие пространства", "nav.boards": "Доски", "nav.tickets": "Заявки",
            "nav.settings": "Настройки", "workspace.create": "Создать рабочее пространство", "board.create": "Создать доску",
            "tickets.new": "Новая заявка", "actions.save": "Сохранить", "actions.cancel": "Отмена"}
TERMS = {  # english word in source -> (required russian stem regex, forbidden regex)
    "workspace": (r"рабоч\w*\s+пространств", r"воркспейс|рабочая область|рабочей области"),
    "board": (r"доск|досок", r"\bборд|панел"),
    "ticket": (r"заявк|заявок", r"тикет|билет"),
}

def flat(d, p=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, p + k + "."))
        else:
            out[p + k] = v
    return out

def expected_keys(en):
    keys = set()
    for k in en:
        m = re.match(r"(.*)_(one|other)$", k)
        if m:
            keys.update(f"{m.group(1)}_{c}" for c in PLURAL_RU)
        else:
            keys.add(k)
    return keys

def load(path):
    try:
        return flat(json.load(open(path, encoding="utf-8-sig"))), None
    except FileNotFoundError:
        return None, "missing file"
    except Exception as e:
        return None, f"invalid JSON: {e}"

def grade(run):
    r = {"run": os.path.basename(run)}
    checks = {}
    total_terms = bad_terms = 0
    for name in ("common", "features"):
        en, _ = load(f"{run}/locales/en/{name}.json")
        ru, err = load(f"{run}/locales/ru/{name}.json")
        if ru is None:
            checks[name] = err
            continue
        exp = expected_keys(en)
        missing = sorted(exp - set(ru))
        plural_missing = [k for k in missing if re.search(r"_(few|many)$", k)]
        other_missing = [k for k in missing if k not in plural_missing]
        broken = []
        for k, v in ru.items():
            base = re.sub(r"_(one|few|many|other)$", "_other", k) if re.search(r"_(one|few|many|other)$", k) else k
            src = en.get(base) or en.get(k)
            if src is not None and sorted(TOK.findall(src)) != sorted(TOK.findall(str(v))):
                broken.append(k)
        untranslated = [k for k, v in ru.items() if k in en and v == en[k] and re.search(r"[A-Za-z]{3}", str(v))]
        checks[name] = {"missing_plural_forms": len(plural_missing), "missing_other": len(other_missing),
                        "broken_tokens": len(broken), "untranslated": len(untranslated)}
        for k, src in en.items():
            for word, (need, forbid) in TERMS.items():
                if re.search(word, TOK.sub("", src), re.I):
                    for rk in [x for x in ru if x == k or re.sub(r"_(one|few|many|other)$", "", x) == re.sub(r"_(one|other)$", "", k)]:
                        total_terms += 1
                        val = str(ru[rk]).lower()
                        if not re.search(need, val) or re.search(forbid, val):
                            bad_terms += 1
        if name == "common":
            checks["existing_changed"] = sum(1 for k, v in EXISTING.items() if ru.get(k) != v)
            post = str(ru.get("actions.post", "")).lower()
            order = str(ru.get("labels.order", "")).lower()
            checks["post_is_publish"] = bool(re.search(r"опублик", post))
            checks["order_is_sort"] = bool(re.search(r"поряд|сортир", order)) and "заказ" not in order
    checks["term_errors"] = f"{bad_terms}/{total_terms}"
    r.update(checks)
    try:
        cfg = open(f"{run}/src/i18n.js", encoding="utf-8").read()
    except Exception:
        cfg = ""
    r["features_registered"] = bool(re.search(r"ru/features", cfg)) and bool(re.search(r"features\s*:", cfg) or "ns:" in cfg)
    r["glossary_file"] = bool(glob.glob(f"{run}/**/*glossar*", recursive=True))
    return r

if __name__ == "__main__":
    runs = sys.argv[1:]
    for run in runs:
        print(json.dumps(grade(run), ensure_ascii=False))
