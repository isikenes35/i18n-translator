# Unicode CLDR Cardinal Plural Rules

Reference table of Unicode CLDR cardinal plural categories for 27 widely localized languages.

- **Primary source:** Unicode CLDR Language Plural Rules — https://www.unicode.org/cldr/charts/latest/supplemental/language_plural_rules.html
- **ICU MessageFormat reference:** https://unicode-org.github.io/icu/userguide/format_parse/messages/
- **i18next v4 pluralization reference:** https://www.i18next.com/translation-function/plurals

## Cardinal Plural Categories by Language

| Language | BCP 47 | CLDR Categories | Integer & Decimal Rule Summary |
| --- | --- | --- | --- |
| **Japanese** | `ja` | `other` | All numbers map to `other`. |
| **Chinese** | `zh` | `other` | All numbers map to `other`. |
| **Korean** | `ko` | `other` | All numbers map to `other`. |
| **Vietnamese** | `vi` | `other` | All numbers map to `other`. |
| **Thai** | `th` | `other` | All numbers map to `other`. |
| **Indonesian** | `id` | `other` | All numbers map to `other`. |
| **English** | `en` | `one`, `other` | `one`: integer `1` (`i = 1, v = 0`); `other`: `0`, `2+`, decimals (`1.0`, `1.5`). |
| **German** | `de` | `one`, `other` | `one`: integer `1` (`i = 1, v = 0`); `other`: `0`, `2+`, decimals. |
| **Dutch** | `nl` | `one`, `other` | `one`: integer `1` (`i = 1, v = 0`); `other`: `0`, `2+`, decimals. |
| **Swedish** | `sv` | `one`, `other` | `one`: integer `1` (`i = 1, v = 0`); `other`: `0`, `2+`, decimals. |
| **Turkish** | `tr` | `one`, `other` | `one`: `n = 1` (`1`, `1.0`); `other`: `0`, `2+`, other decimals. Nouns stay singular after numbers, but phrasing can still differ for `1` vs `other`. |
| **Hungarian** | `hu` | `one`, `other` | `one`: `n = 1`; `other`: `0`, `2+`, other decimals. |
| **Greek** | `el` | `one`, `other` | `one`: `n = 1`; `other`: `0`, `2+`, other decimals. |
| **Finnish** | `fi` | `one`, `other` | `one`: integer `1` (`i = 1, v = 0`); `other`: `0`, `2+`, decimals. |
| **Hindi** | `hi` | `one`, `other` | `one`: `i = 0` or `n = 1` (covers both `0` and `1`, plus `0.x`); `other`: `2+`, `1.5`. |
| **French** | `fr` | `one`, `many`\*, `other` | `one`: `i = 0..1` (`0`, `1`, `0.5`, `1.5`); `many`\*: exact million multiples / compact exponents (`1000000`, `1c6`); `other`: `2+`. |
| **Portuguese** | `pt` | `one`, `many`\*, `other` | `one`: `i = 0..1` (Brazilian `pt`; European `pt-PT` uses `i = 1, v = 0`); `many`\*: exact million multiples / compact exponents; `other`: everything else. |
| **Spanish** | `es` | `one`, `many`\*, `other` | `one`: `n = 1`; `many`\*: exact million multiples / compact exponents (`1 millón de ...`); `other`: `0`, `2+`, decimals. |
| **Italian** | `it` | `one`, `many`\*, `other` | `one`: `i = 1, v = 0`; `many`\*: exact million multiples / compact exponents; `other`: `0`, `2+`, decimals. |
| **Hebrew** | `he` | `one`, `two`, `other` | `one`: `i = 1, v = 0` or `i = 0, v != 0`; `two`: integer `2` (dual form); `other`: `0`, `3+`, other decimals. |
| **Romanian** | `ro` | `one`, `few`, `other` | `one`: `i = 1, v = 0`; `few`: `v != 0` or `n = 0` or (`n != 1` and `n % 100 = 1..19`) (e.g., `0`, `2–19`, `101`, `1.5`); `other`: `20–100`, `120–200`, etc. |
| **Russian** | `ru` | `one`, `few`, `many`, `other` | `one`: ends in `1` except `11` (`1, 21, 31, 101`); `few`: ends in `2–4` except `12–14` (`2, 3, 4, 22`); `many`: ends in `0`, `5–9`, `11–14` (`0, 5, 11, 20`); `other`: decimals (`1.5`). |
| **Ukrainian** | `uk` | `one`, `few`, `many`, `other` | Same integer split as Russian (`one`, `few`, `many`); `other`: decimals. |
| **Polish** | `pl` | `one`, `few`, `many`, `other` | `one`: integer `1`; `few`: ends in `2–4` except `12–14` (`2, 3, 4, 22`); `many`: `0`, ends in `0–1` (except `1`), `5–9`, `12–14` (`5, 12, 21`); `other`: decimals (`1.5`). |
| **Czech** | `cs` | `one`, `few`, `many`, `other` | `one`: integer `1`; `few`: integers `2–4`; `many`: decimals (`v != 0`, e.g. `1.5`); `other`: `0`, `5+`. |
| **Slovak** | `sk` | `one`, `few`, `many`, `other` | Same structure as Czech (`one`: `1`, `few`: `2–4`, `many`: decimals, `other`: `0`, `5+`). |
| **Arabic** | `ar` | `zero`, `one`, `two`, `few`, `many`, `other` | `zero`: `0`; `one`: `1`; `two`: `2`; `few`: `n % 100 = 3..10`; `many`: `n % 100 = 11..99`; `other`: `100–102`, `200–202`, decimals. |

\* **Note on `many` in Romance languages (`fr`, `es`, `it`, `pt`):** CLDR added `many` to support compact/round-million phrases such as French `"1 million d'articles"` or Spanish `"1 millón de archivos"`. For ordinary UI counts below one million, only `one` and `other` trigger; if `many` is omitted, ICU and i18next fall back to `other`. Include `many` when formatting compact or million-scale counters, or when enforcing strict CLDR parity.

## Practical Traps Agents Often Hit

1. **Hardcoding `1` in the `one` branch:** In English, `one` only matches `1`, so `"1 item"` works. In Russian and Ukrainian, `one` also matches `21`, `31`, `101`. Always keep the numeric placeholder (`{{count}}` or `#`) in the `one` form for languages where `one` matches values other than `1`. Use an exact `=1` branch in ICU if you need special phrasing strictly for `1`.
2. **Omitting `other` in Slavic languages:** Even though integers in Russian, Ukrainian, and Polish all fall into `one`, `few`, or `many`, decimals (`1.5`) use `other` and ICU/i18next require `other` as the fallback branch. Always provide all four (`one`, `few`, `many`, `other`).
3. **Treating `0` as plural in French or Hindi:** In French (`fr`) and Hindi (`hi`), `0` maps to `one`, not `other`. If zero needs special wording (`"Aucun élément"` / `"No items"`), use `=0` in ICU or `_zero` in i18next.
4. **Copying English `_one`/`_other` into 1-form languages:** In Japanese, Chinese, Korean, Vietnamese, Thai, and Indonesian, `Intl.PluralRules` only resolves `other`. In i18next v4, supply `key_other` (or a single non-plural key if the codebase does not pass `count`).
5. **Checking unlisted locales:** For any locale not in this table, look up its cardinal rule on the official Unicode CLDR chart above or inspect `Intl.PluralRules(locale).resolvedOptions().pluralCategories` in Node.js.
