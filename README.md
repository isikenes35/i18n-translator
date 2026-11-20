# i18n-translator

A skill (instruction file) for AI coding agents such as Claude Code that asks the agent to translate and check i18n locale files while keeping project terminology, plural rules, placeholders, and ICU syntax intact.

## Why

- Across large files or multiple namespaces, an agent often translates the same product term in different ways (terminology drift).
- When translating from English to languages with more plural forms (such as Russian, Polish, Czech, or Arabic), an agent often copies only `_one` and `_other` and misses required CLDR categories.
- Without reading the codebase, an agent guesses ambiguous UI words (such as `Back`, `Lead`, or `Close`) out of context.
- An agent can break ICU MessageFormat braces, translate `select` or `plural` keywords, drop HTML/JSX tags, or alter placeholder variable names.

## What it does

- Asks the agent to detect the project's localization library, file format, and locale layout from package manifests and config files before translating.
- Asks the agent to search the codebase for ambiguous keys to check where they appear in the UI and note unresolved ambiguities.
- Uses a project-level `i18n-glossary.json` file (`references/glossary-workflow.md`) to store canonical translations, `doNotTranslate` terms, inflected `acceptedForms`, and tone notes across files, chunks, and sessions.
- Points the agent to `references/plural-rules.md` (Unicode CLDR cardinal plural categories for 27 languages) and `references/formats-and-placeholders.md` (i18next, FormatJS/react-intl, vue-i18n, Angular, Laravel, `.resx`, `.po`, Android `strings.xml`, Apple `.xcstrings`/`.strings`, and `.properties`).
- Adds missing keys from the source file and reports extra target keys without deleting them unless asked.
- Asks the agent to register any new locale file or namespace in the app's i18n config, so the app actually loads it.
- Runs `scripts/validate_i18n.py` to check missing/extra keys, placeholders, HTML/JSX tags, ICU syntax, required CLDR plural categories, unchanged values, and glossary consistency, then fixes errors before finishing.

## Files

- `SKILL.md`: Main skill instructions and 8-step localization workflow.
- `references/formats-and-placeholders.md`: Placeholder, plural, and escaping syntax across common i18n formats and ICU MessageFormat, with official documentation URLs.
- `references/plural-rules.md`: Unicode CLDR cardinal plural categories for 27 languages and common pluralization traps.
- `references/glossary-workflow.md`: Schema for `i18n-glossary.json` and steps for translating large or multi-file projects consistently.
- `scripts/validate_i18n.py`: Python 3 validator (standard library only; optional PyYAML for YAML) supporting `json-i18next`, `json-icu`, `yaml-i18next`, `yaml-icu`, `properties`, and `po`, with human-readable and `--json` output.
- `tests/run_tests.py` and `tests/fixtures/`: Automated tests and sample fixtures covering valid and broken translations.
- `eval/`: A with/without-skill comparison on a small React + i18next app, with graders, raw results and `eval/RESULTS.md`.
- `README.md`: This overview.

## Install

Copy this folder into your Claude Code skills directory (or the skills directory used by Cursor, Codex, or Antigravity):

```bash
cp -r i18n-translator ~/.claude/skills/i18n-translator
```

Running `scripts/validate_i18n.py` requires Python 3 (standard library only; install PyYAML if you validate YAML files).

To run the included tests:

```bash
python3 tests/run_tests.py
```

On Windows, run `py -3 tests/run_tests.py`.

## Test results

Full details are in `eval/RESULTS.md`.

- **Scale test** (gemini-4-hydrogen-low and -high, 2 runs per condition each). The task was 221 keys in 6 files, translated into Russian over 3 separate agent sessions.
  - Without the skill, 92-98 of about 280 term checks failed. Later sessions switched the existing word for "ticket" ("заявка") to other words.
  - With the skill, 0 term checks failed.
  - Every new namespace was registered in the app config with the skill (5/5) and none without it (0/5).
  - With a larger model (gemini-4-hydrogen-high), there were no term errors with or without the skill. The difference that remained was registering the new namespaces in the app config: 5/5 with the skill, 0/5 without it.
- **Small test** (30 keys, 2 sessions; 3 runs per condition with gemini-4-hydrogen-medium, gemini-4-hydrogen-low and Claude Haiku).
  - The translations were mostly correct with or without the skill. The one exception was a no-skill hydrogen-low run that dropped all `_other` plural forms.
  - The main difference was the new file. With the current skill it was registered in the app config every time; without the skill, in 1 of 9 runs.

## Status

A personal project. The tests above are small: few runs, one target language (Russian) and one framework (i18next).
