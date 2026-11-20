"""Scale fixture: 6 namespaces, ~330 keys, generated from templates around 3 domain terms."""
import json, os, shutil
F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture")
shutil.rmtree(F, ignore_errors=True)
TERMS = {"workspace": "workspaces", "board": "boards", "ticket": "tickets"}
ACT = ["Create", "Rename", "Archive", "Delete", "Duplicate", "Share", "Export", "Restore", "Move", "Pin"]
MSG = ["{T} created", "{T} renamed to {{{{name}}}}", "{T} archived by {{{{user}}}}", "Could not delete this {t}",
       "This {t} is read-only", "You do not have access to this {t}", "Search {ts}", "No {ts} yet", "All {ts}",
       "Recent {ts}", "Favorite {ts}", "Shared {ts}", "{T} settings", "{T} members", "{T} owner",
       "Leave {t}", "Are you sure you want to delete <strong>{{{{name}}}}</strong>?", "Open {t} in a new tab"]
def ns_for(term):
    t, ts = term, TERMS[term]; T = t.capitalize()
    d = {"actions": {a.lower(): f"{a} {t}" for a in ACT},
         "messages": {f"m{i:02d}": m.format(t=t, ts=ts, T=T) for i, m in enumerate(MSG)},
         "counts": {f"{ts}_one": f"{{{{count}}}} {t}", f"{ts}_other": f"{{{{count}}}} {ts}",
                    f"selected_one": f"{{{{count}}}} {t} selected", f"selected_other": f"{{{{count}}}} {ts} selected",
                    f"archived_one": f"{{{{count}}}} archived {t}", f"archived_other": f"{{{{count}}}} archived {ts}"},
         "empty": {"title": f"No {ts} here", "body": f"Create your first {t} to get started.", "cta": f"New {t}"}}
    for x in ["filters", "sort", "bulk"]:
        d[x] = {f"k{i}": f"{x.capitalize()} {ts} option {i}" if False else s for i, s in enumerate(
            [f"{T} name", f"{T} status", f"Last updated {t}", f"Oldest {ts} first", f"Newest {ts} first",
             f"Only my {ts}", f"Hide archived {ts}", f"Group {ts} by owner"])}
    return d
def cross():
    d = {"reports": {}, "settings": {}}
    for i, (a, b) in enumerate([(a, b) for a in TERMS for b in TERMS if a != b]):
        d["reports"][f"r{i}"] = f"{TERMS[b].capitalize()} per {a}"
        d["reports"][f"r{i}_hint"] = f"Shows how many {TERMS[b]} each {a} has."
        d["settings"][f"s{i}"] = f"Allow moving {TERMS[b]} between {TERMS[a]}"
    d["reports"].update({"title": "Reports", "export": "Export report", "range": "Date range",
                         "tickets_closed_one": "{{count}} ticket closed", "tickets_closed_other": "{{count}} tickets closed"})
    d["settings"].update({"title": "Settings", "language": "Language", "theme": "Theme", "notifications": "Notifications",
                          "post": "Post", "order": "Order"})
    return d
os.makedirs(F + "/locales/en"); os.makedirs(F + "/locales/ru"); os.makedirs(F + "/src")
files = {"workspaces": ns_for("workspace"), "boards": ns_for("board"), "tickets": ns_for("ticket")}
c = cross(); files["reports"] = {"reports": c["reports"]}; files["settings"] = {"settings": c["settings"]}
files["common"] = {"nav": {"workspaces": "Workspaces", "boards": "Boards", "tickets": "Tickets", "settings": "Settings", "reports": "Reports"},
                   "actions": {"save": "Save", "cancel": "Cancel", "post": "Post", "close": "Close"}}
for n, d in files.items():
    json.dump(d, open(f"{F}/locales/en/{n}.json", "w", encoding="utf-8"), indent=2)
json.dump({"nav": {"workspaces": "Рабочие пространства", "boards": "Доски", "tickets": "Заявки", "settings": "Настройки", "reports": "Отчёты"},
           "actions": {"save": "Сохранить", "cancel": "Отмена", "post": "Опубликовать", "close": "Закрыть"}},
          open(f"{F}/locales/ru/common.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
open(f"{F}/src/i18n.js", "w").write("""import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from '../locales/en/common.json';
import ru from '../locales/ru/common.json';
i18n.use(initReactI18next).init({ resources: { en: { common: en }, ru: { common: ru } }, lng: 'ru', fallbackLng: 'en', defaultNS: 'common' });
export default i18n;
""")
open(f"{F}/src/SettingsPanel.jsx", "w").write("""import { useTranslation } from 'react-i18next';
export function SettingsPanel({ onPublish, sortBy, setSortBy }) {
  const { t } = useTranslation('settings');
  return (<div>
    <label>{t('settings.order')}<select value={sortBy} onChange={e => setSortBy(e.target.value)}><option value="az">A-Z</option></select></label>
    <button onClick={onPublish}>{t('settings.post')}</button>
  </div>);
}
""")
open(f"{F}/package.json", "w").write('{"name":"taskboard","dependencies":{"i18next":"^23.0.0","react-i18next":"^14.0.0","react":"^18.0.0"}}\n')
def count(d): return sum(count(v) if isinstance(v, dict) else 1 for v in d.values())
print({n: count(d) for n, d in files.items()}, "total", sum(count(d) for d in files.values()))
