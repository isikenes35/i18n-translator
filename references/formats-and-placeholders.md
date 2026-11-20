# i18n File Formats, Placeholders, and ICU Syntax

Reference for detecting and preserving placeholders, pluralization rules, and escaping across common localization formats.

## Format Comparison Table

| Format / Library | Typical Files | Placeholder Syntax | Pluralization Mechanism | Official Documentation |
| --- | --- | --- | --- | --- |
| **i18next** (JSON v4) | `locales/<lng>/<ns>.json` | `{{name}}`, `{{- raw}}`, `{{val, format}}`, `$t(key)` | CLDR suffixes appended to key: `_zero`, `_one`, `_two`, `_few`, `_many`, `_other`. Context precedes plural: `key_context_one`. | https://www.i18next.com/translation-function/plurals , https://www.i18next.com/translation-function/interpolation , https://www.i18next.com/translation-function/context |
| **FormatJS / react-intl** | `lang/<lng>.json`, `messages/<lng>.json` | `{name}`, `{count, number}`, `<tag>...</tag>` | Full ICU MessageFormat (`plural`, `select`, `selectordinal`) inside the string value. | https://formatjs.io/docs/react-intl/ , https://formatjs.io/docs/core-concepts/icu-syntax/ |
| **vue-i18n** | `locales/<lng>.json`, `.yaml` | `{name}`, `{0}`, `@:other.key` | Pipe-separated choices (`no apples \| one apple \| {count} apples`); custom plural rule function needed for Slavic/Arabic unless ICU plugin is configured. | https://vue-i18n.intlify.dev/guide/essentials/syntax.html , https://vue-i18n.intlify.dev/guide/essentials/pluralization.html |
| **Angular i18n** | `messages.<lng>.xlf`, `.xmb`, `.json` | `{{expr}}` in templates; `<x id="INTERPOLATION"/>` in XLIFF | ICU expressions (`plural`, `select`) inside `i18n` elements and extracted XLIFF units. | https://angular.dev/guide/i18n |
| **Laravel** | `lang/<lng>/*.php`, `lang/<lng>.json` | `:name`, `:Name`, `:NAME` (case-sensitive capitalization) | Pipe `\|` choices and explicit counts/ranges (`{0} None \| [1,*] :count items`). | https://laravel.com/docs/localization |
| **.NET (`.resx`)** | `Resources.<lng>.resx` | `{0}`, `{1}`, `{0:N2}` (`string.Format`) | No native plural syntax in `.resx`; projects use separate keys (`Items_One`, `Items_Other`) or a library such as SmartFormat. | https://learn.microsoft.com/en-us/dotnet/core/extensions/localization |
| **GNU gettext** | `locale/<lng>/LC_MESSAGES/*.po`, `.pot` | `%s`, `%d`, `%1$s`, `%(name)s`, `{name}` (runtime-dependent) | `msgid_plural` with indexed `msgstr[0]`, `msgstr[1]`, ... governed by the `Plural-Forms` header (`nplurals=N; plural=...;`). | https://www.gnu.org/software/gettext/manual/gettext.html |
| **Android** | `res/values-<lng>/strings.xml` | `%1$s`, `%2$d`, `%.2f` (use positional specifiers when >1 arg) | `<plurals name="..."><item quantity="one">...</item><item quantity="other">...</item></plurals>`. Escape apostrophes as `\'`. | https://developer.android.com/guide/topics/resources/string-resource |
| **Apple (iOS / macOS)** | `Localizable.xcstrings`, `.strings`, `.stringsdict` | `%@`, `%1$@`, `%lld`, `%d`, `%f` | `.xcstrings` JSON `variations.plural` (`zero`/`one`/`two`/`few`/`many`/`other`); legacy `.stringsdict` XML plist. | https://developer.apple.com/documentation/Xcode/localizing-and-varying-text-with-a-string-catalog |
| **Java `.properties`** | `messages_<lng>.properties` | `{0}`, `{1}`, `{0,number}` (`MessageFormat`) | Embedded ICU/MessageFormat `choice` or ICU4J `plural`; double apostrophes `''` when passed through `java.text.MessageFormat`. | https://unicode-org.github.io/icu/userguide/format_parse/messages/ |

## ICU MessageFormat Rules

Official reference: https://unicode-org.github.io/icu/userguide/format_parse/messages/

### 1. Argument Skeletons (Never Translate Keywords or Variable Names)

- **Simple placeholder:** `{userName}` — keep `userName` verbatim.
- **`plural` (cardinal):**
  ```icu
  {count, plural,
    =0 {No files selected}
    one {# file selected}
    other {# files selected}
  }
  ```
  - Always include `other`.
  - Add every CLDR category required by the target locale (see `plural-rules.md`).
  - Never translate `plural`, `offset`, `zero`, `one`, `two`, `few`, `many`, or `other`.
  - `#` inside a `plural` branch formats the numeric value (`count - offset`) using target locale digits and separators. Do not replace `#` with `{count}` when `offset:` is present, because `offset` adjusts `#` but not `{count}`.
- **`select` (categorical / gender / role):**
  ```icu
  {gender, select,
    female {She shared a link.}
    male {He shared a link.}
    other {They shared a link.}
  }
  ```
  - Always include `other`.
  - Never translate selector branch keys (`female`, `male`, `admin`, `other`). Translate only the text inside `{...}`.
- **`selectordinal` (ordinals):**
  ```icu
  {rank, selectordinal,
    one {#st place}
    two {#nd place}
    few {#rd place}
    other {#th place}
  }
  ```
  - Always include `other`; adapt ordinal categories to the target language's ordinal rules.

### 2. Nesting Order

When combining `select` and `plural`, keep `select` on the outside and `plural` on the inside, and translate complete sentences in each leaf branch rather than concatenating fragments:

```icu
{gender, select,
  female {{count, plural,
    one {She invited # guest.}
    other {She invited # guests.}
  }}
  male {{count, plural,
    one {He invited # guest.}
    other {He invited # guests.}
  }}
  other {{count, plural,
    one {They invited # guest.}
    other {They invited # guests.}
  }}
}
```

### 3. Escaping Rules

- Literal `{`, `}`, or `#` (inside `plural`) must be quoted with ASCII single quotes: `'{'`, `'}'`, `'#'`.
- A literal ASCII apostrophe `'` is escaped as `''` when quoting is active (and always `''` in legacy `java.text.MessageFormat`).
- In modern ICU (4.8+), an ASCII apostrophe only starts quoting when immediately followed by a syntax character (`{`, `}`, `#`, `|`, or `'`). Using typographic apostrophes (`’`, U+2019) in prose avoids accidental quoting in languages like French or Italian (`l’article`), unless the project style explicitly requires ASCII `'`.

## Format-Specific Pitfalls

- **i18next v3 vs v4:** Check `compatibilityJSON` in the project's i18next config. v4 (default since i18next v21) uses CLDR suffixes (`_one`, `_few`, `_many`, `_other`). Legacy v3 used `_plural` and numeric `_0`/`_1`/`_2`. Match the project's configured version.
- **i18next context + plural:** Always place `_context` before `_pluralCategory` (`friend_female_few`, never `friend_few_female`).
- **Laravel capitalization:** `:name`, `:Name`, and `:NAME` produce lowercase, capitalized, and uppercase substitutions respectively. Preserve exact casing.
- **Positional format specifiers (`%s`, `%d`, `%@`):** When target grammar reorders two placeholders, switch to positional indices (`%2$s ... %1$s` in Android/gettext, `%2$@ ... %1$@` in Apple) instead of swapping values silently.
- **HTML / JSX / react-i18next `<Trans>`:** Keep tag names, closing tags, self-closing slashes, and non-translatable attributes (`href`, `className`, `target`, `rel`, `<0>...</0>`) intact. Only translate human-readable attributes (`title`, `alt`, `aria-label`) if they already exist in the source string.
