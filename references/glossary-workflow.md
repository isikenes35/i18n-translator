# Glossary and Multi-File Consistency Workflow

Large apps split UI copy across many files, namespaces, and sessions. Without a persistent glossary, agents drift on core terms (for example, translating `Workspace` as three different words across navigation, settings, and billing). Keep a single `i18n-glossary.json` file in the repository (at the repo root or inside the locales directory) and read/update it on every translation pass.

## Schema: `i18n-glossary.json`

```json
{
  "version": 1,
  "sourceLocale": "en",
  "styleNotes": {
    "ru": "Use polite 'вы' (lowercase in UI), concise verb infinitives on buttons.",
    "tr": "Use polite 'siz', keep button labels short.",
    "de": "Use formal 'Sie' unless existing files use 'du'."
  },
  "doNotTranslate": [
    "AcmeCloud",
    "API",
    "OAuth",
    "CLI",
    "JSON"
  ],
  "terms": [
    {
      "source": "Workspace",
      "context": "Top-level team container in sidebar and settings",
      "translations": {
        "ru": "Рабочее пространство",
        "de": "Arbeitsbereich",
        "tr": "Çalışma alanı"
      },
      "acceptedForms": {
        "ru": ["рабочего пространства", "рабочем пространстве", "рабочему пространству", "рабочие пространства"]
      },
      "avoid": {
        "ru": ["Проект", "Кабинет"]
      },
      "notes": "Do not confuse with Project."
    },
    {
      "source": "Billing",
      "context": "Subscription and invoice management section",
      "translations": {
        "ru": "Оплата",
        "de": "Abrechnung",
        "tr": "Faturalandırma"
      },
      "acceptedForms": {
        "ru": ["оплаты", "оплате", "оплату"]
      }
    }
  ]
}
```

### Field Definitions

| Field | Required | Purpose |
| --- | --- | --- |
| `version` | Yes | Schema version (`1`). |
| `sourceLocale` | Yes | BCP 47 code of the source language (for example, `en`). |
| `styleNotes` | No | Per-locale tone, formality (`du`/`Sie`, `sen`/`siz`, `ты`/`вы`), punctuation, and button-label conventions. |
| `doNotTranslate` | No | Brand names, product names, acronyms, and technical tokens that must stay verbatim in every locale. |
| `terms` | Yes | List of domain term entries. |
| `terms[].source` | Yes | Source-language term (singular/base form). |
| `terms[].context` | No | Disambiguates overloaded words (for example, `Lead` as sales prospect vs typography). |
| `terms[].translations` | Yes | Map of target locale code (`ru`, `de`, `tr`, ...) to the canonical target translation. |
| `terms[].acceptedForms` | No | Optional map of target locale code to a list of inflected/cased variant strings allowed by `scripts/validate_i18n.py` (useful for Slavic, Turkic, Uralic, and Arabic morphology). |
| `terms[].avoid` | No | Optional map of target locale code to a list of discouraged synonym strings to flag as warnings if an agent slips into them. |
| `terms[].notes` | No | Extra guidance for translators and agents. |

## Multi-File and Large-File Workflow

### 1. Bootstrap Before Translating
- Check if `i18n-glossary.json` already exists in the repo root or locale directory (`locales/`, `src/i18n/`, `messages/`).
- If it exists, read it first and adopt its tone, `doNotTranslate` entries, and `terms`.
- If it does not exist:
  - If target locale files already have partial translations, mine existing translated values for recurring UI terms (navigation items, primary entities, statuses, common buttons) so new translations match existing UI copy.
  - Scan the source files for product names, recurring nouns (appearing 2+ times), and navigation/action labels, and create `i18n-glossary.json`.

### 2. Chunking Large Files Without Losing Context
When a single locale file exceeds ~150 keys (or would risk truncation in one pass):
1. Split along natural top-level object keys or namespaces (for example, `auth`, `dashboard`, `billing`, `settings`).
2. Translate one section at a time while keeping `i18n-glossary.json` in context.
3. Whenever a section introduces a new recurring domain term, add it to `i18n-glossary.json` immediately before moving to the next section.
4. Merge all translated sections back into the target file in the exact key order of the source file.

### 3. Cross-File and Cross-Session Consistency
- Before starting each new file (for example, moving from `common.json` to `billing.json`), re-read `i18n-glossary.json`.
- Never silently change an established glossary term for one screen; if a term genuinely has two distinct meanings, create two entries distinguished by `context`.
- After writing each target file, run `validate_i18n.py` with `--glossary path/to/i18n-glossary.json` to catch drift and dropped `doNotTranslate` tokens.

## Automated Check Behavior

When `--glossary` is passed to `scripts/validate_i18n.py`:
- Missing `doNotTranslate` terms (present in source, absent in target) produce a `glossary_dnt_missing` **warning**.
- A term in `terms[]` whose `source` appears in the source value (case-insensitive word match) is checked against `translations[locale]` and `acceptedForms[locale]` (case-insensitive substring match). If none match, or if a term in `avoid[locale]` appears, the validator emits a `glossary_mismatch` **warning**.
- Glossary checks emit **warnings** (exit code `0`) rather than hard errors because inflected forms in agglutinative or fusional languages may legitimately differ from the base lemma; review every warning and either fix the translation or add the valid inflection to `acceptedForms`.
