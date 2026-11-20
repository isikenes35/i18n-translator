---
name: i18n-translator
description: Localize and maintain i18n message files across any source and target language while preserving project context, terminology consistency, CLDR plural forms, ICU MessageFormat syntax, placeholders, and markup. Use when adding a new language, translating or updating locale files (i18next, FormatJS/react-intl, vue-i18n, Angular, Laravel, .NET .resx, gettext .po, Android strings.xml, Apple .xcstrings/.strings, Java .properties), syncing missing keys, or validating translations in Claude Code, Cursor, Codex, or Antigravity.
---

# i18n-translator

Translate and maintain application locale files without losing domain terminology, UI context, plural grammar, or placeholder/ICU integrity.

## References and Tools

Read the relevant reference before editing target files:
- `references/formats-and-placeholders.md` — placeholder, plural, and escaping syntax for i18next, FormatJS/react-intl, vue-i18n, Angular, Laravel, `.resx`, `.po`, Android `strings.xml`, Apple `.xcstrings`/`.strings`, and `.properties`, plus ICU MessageFormat rules.
- `references/plural-rules.md` — Unicode CLDR cardinal plural categories for 27 common languages and common pluralization traps.
- `references/glossary-workflow.md` — `i18n-glossary.json` schema and chunking/multi-file consistency workflow.
- `scripts/validate_i18n.py` — automated validator (Python 3 stdlib only; optional PyYAML for YAML).

## Workflow

Follow these steps in order. Do not skip project discovery, glossary loading, or validation.

### 1. Discover the Project i18n Setup

Inspect the repository before translating a single key:
- **Dependencies & config:** Check `package.json`, `composer.json`, `*.csproj`, `build.gradle*`, `*.xcodeproj`, and i18n configs (`i18n.*`, `next-i18next.config.*`, `angular.json`, `nuxt.config.*`, `vite.config.*`). Identify the exact library and format version (for example, i18next v4 CLDR suffixes vs legacy v3 `_plural`).
- **Locale layout:** Locate source and target locale directories (for example, `locales/en/`, `src/i18n/`, `lang/`, `res/values-*`, `Localizable.xcstrings`). Confirm the source locale (often `en`) and target BCP 47 locale code(s).
- **Existing conventions:** If target locale files already exist, read a sample to match established formality (`du`/`Sie`, `sen`/`siz`, `ты`/`вы`), capitalization style, and punctuation.

### 2. Establish Context from Code

Never translate isolated ambiguous keys blindly (`Back`, `Lead`, `Close`, `Run`, `Charge`, `Post`, `Save`):
- Grep the codebase for the key (including namespace or `useTranslation('ns')` / `keyPrefix` patterns) to see where it renders: button, nav tab, heading, tooltip, placeholder, validation error, toast, or status badge.
- Check sibling keys and parent object names for domain cues.
- **UI length constraints:** For buttons, tabs, table headers, and badges, prefer concise target-language equivalents rather than literal expansions that clip layouts (especially in German, Finnish, Russian, or Greek).
- **Unresolved ambiguity:** If a key is unused in code and genuinely ambiguous, choose the most likely meaning based on sibling keys and record a brief note in your final summary (or in `i18n-glossary.json` notes) for review—unless the user requested raw file-only stdout.

### 3. Load or Create the Project Glossary (`i18n-glossary.json`)

Terminology drift across large files, namespaces, and sessions is a primary localization failure. Use `i18n-glossary.json` (schema in `references/glossary-workflow.md`):
- Search for an existing `i18n-glossary.json` in the repository root or locale directory. Read it first and obey its `styleNotes`, `doNotTranslate`, `terms`, and `avoid` lists.
- If no glossary exists:
  1. If target files already contain translations, mine existing translated values for recurring UI concepts so new strings stay consistent with the existing UI.
  2. Extract recurring domain nouns, navigation labels, statuses, and product/brand names from source files and create `i18n-glossary.json`.
- **Large files (> ~150 keys) and multi-file runs:** Split work along top-level sections or namespaces. Keep `i18n-glossary.json` in context for every chunk, and append newly settled recurring terms immediately before moving to the next chunk or file.

### 4. Handle Plurals and `select` Correctly

Consult `references/plural-rules.md` for the target locale's CLDR cardinal categories before generating plural entries:
- **Generate all required target categories** regardless of how many the source language has:
  - Example (i18next v4, `en` -> `ru`): expand `items_one` + `items_other` into `items_one`, `items_few`, `items_many`, and `items_other`.
  - Example (ICU `plural`, `en` -> `ar`): expand `one` + `other` into `zero`, `one`, `two`, `few`, `many`, and `other`.
  - Example (`en` -> `ja`/`zh`/`ko`/`vi`/`th`/`id`): only `other` is required.
- **Keep numeric placeholders in `one` when needed:** In Russian, Ukrainian, and several other languages, `one` matches `21`, `31`, `101` as well as `1`. Never hardcode `"1 ..."` inside the `one` branch—keep `{{count}}` or `#` (use exact `=1` in ICU if you need special phrasing strictly for `1`).
- **Context + plural order (i18next):** Always put `_context` before `_plural` (`friend_female_few`, never `friend_few_female`).
- **ICU rules:** Keep `plural`, `select`, `selectordinal`, `offset:N`, CLDR category keywords (`zero`/`one`/`two`/`few`/`many`/`other`), and `select` branch keys (`male`, `female`, `admin`, `other`) untranslated. Always include `other`. Keep `select` outside `plural` when nested, and translate full sentences in each leaf branch.

### 5. Preserve Structure, Placeholders, Markup, and RTL Safety

Consult `references/formats-and-placeholders.md` for exact format rules:
- **Keys:** Keep all object keys and nesting unchanged (except locale-appropriate plural suffixes in i18next or `<item quantity="...">` / `msgstr[n]` variants).
- **Placeholders:** Preserve exact variable names, delimiters, and casing (`{{name}}`, `{count}`, `:Name`, `%1$s`, `%@`, `{0}`). When target word order swaps two unnamed printf/Apple specifiers (`%s`, `%@`), convert to positional specifiers (`%2$s ... %1$s`, `%2$@ ... %1$@`).
- **HTML / JSX / `<Trans>`:** Keep tag names, closing tags, self-closing slashes, numeric tags (`<0>...</0>`), and code attributes (`href`, `className`, `target`, `rel`, `id`) intact. Only translate user-facing text and existing human-readable attributes (`title`, `alt`, `aria-label`).
- **Do not translate:** Brand/product names, code identifiers, CLI commands, API endpoints, URLs, email addresses, file paths, and `doNotTranslate` glossary entries.
- **RTL languages (`ar`, `he`, `fa`, `ur`):** Write natural target-language sentences with placeholders and inline tags in logical reading order. Do not insert raw Unicode bidi override control characters (`\u202E`, `\u202A`) to patch layout; leave directionality to CSS/UI `dir="rtl"`.

### 6. Sync Missing Keys Without Deleting Extra Keys

When updating an existing target file against a source file:
- Add every key present in the source file that is missing from the target file, matching the source key order and indentation.
- Do **not** delete keys that exist only in the target file unless the user explicitly asks to prune them. Report extra target keys in your summary so the user can decide.
- Preserve existing valid translations unless they violate placeholders, ICU syntax, plural rules, or explicit glossary fixes requested by the user.
- **New files or namespaces must be wired in.** If you create a locale file that did not exist before (a new namespace such as `features.json`, or a whole new locale), find where the app loads translations (`i18n.js`/`i18n.ts` `resources`, `ns` lists, backend `loadPath`, `next-i18next.config.*`, Laravel/Rails auto-loading, `.csproj` resource includes, Xcode/Android resource folders) and register it for every locale, matching how existing files are registered. If loading is automatic, say so in your report. A translation file the app never loads is a bug.

### 7. Validate and Repair Before Finishing

Run the validation script against every modified target file (JSON/YAML i18next, JSON/YAML ICU, `.properties`, `.po`):

```bash
python3 scripts/validate_i18n.py <source-file> <target-file> --locale <bcp47> --format <format> --glossary i18n-glossary.json
```

(Use `py -3` on Windows if `python3` is unavailable. Supported `--format` values: `auto`, `json-i18next`, `json-icu`, `yaml-i18next`, `yaml-icu`, `properties`, `po`. With `--format auto`, JSON/YAML files are detected as `json-icu`/`yaml-icu` only when source values contain complex ICU blocks (`plural`/`select`/`selectordinal`) and no `{{...}}` placeholders or CLDR `_one`/`_other` key suffixes; otherwise `auto` defaults to `i18next`, so pass `--format json-icu` explicitly for ICU files with only simple `{var}` placeholders. Pass `--strict-romance-many` to require the CLDR `many` category for `fr`/`es`/`it`/`pt` (for compact or million-scale counters; by default only `one` and `other` are required), and pass `--json` for machine-readable output.)

- **Exit code `1` (errors):** Missing keys, missing required CLDR plural categories, placeholder mismatches, unbalanced/mismatched HTML/JSX tags, or broken ICU syntax / missing `other` / translated `select` keys. Fix every error and re-run until exit code is `0`.
- **Exit code `0` with warnings:** Extra target keys, values identical to source, hardcoded digits or missing `count` placeholders in `*_one` forms for multi-integer-`one` locales (`plural_hardcoded_one`), or glossary mismatches. Inspect every warning: fix real drift or untranslated strings, or add legitimate inflected forms to `acceptedForms` in `i18n-glossary.json`.
- For formats outside the script (`.resx`, `strings.xml`, `.xcstrings`, `.xlf`, PHP arrays), run the project's native XML/JSON/PHP parser or linter to verify syntax, placeholders, and plural entries.

### 8. Output Behavior

- **Repository tasks (default):** Write changes directly to the target locale file(s) and `i18n-glossary.json`. After validation passes, give a concise report listing updated files, validator results, any extra keys kept, and any ambiguous keys flagged.
- **Raw-content requests:** If the user passes an inline snippet or explicitly asks for raw file content only, output ONLY the valid translated file content with zero surrounding prose or markdown commentary.
