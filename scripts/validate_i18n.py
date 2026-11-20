#!/usr/bin/env python3
"""Validate translated i18n files against a source locale file.

Uses only the Python 3 standard library (PyYAML is imported optionally for YAML
formats).

Exit codes:
  0 - No errors (warnings may still be present)
  1 - One or more errors found, or invalid input / parse failure
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import re
import sys
from typing import Any

# Unicode CLDR cardinal plural categories required for common locales.
# Source: https://www.unicode.org/cldr/charts/latest/supplemental/language_plural_rules.html
CLDR_REQUIRED_CATEGORIES: dict[str, list[str]] = {
    # 1 form
    "ja": ["other"],
    "zh": ["other"],
    "ko": ["other"],
    "vi": ["other"],
    "th": ["other"],
    "id": ["other"],
    # 2 forms
    "en": ["one", "other"],
    "de": ["one", "other"],
    "nl": ["one", "other"],
    "sv": ["one", "other"],
    "tr": ["one", "other"],
    "hu": ["one", "other"],
    "el": ["one", "other"],
    "fi": ["one", "other"],
    "hi": ["one", "other"],
    # Romance languages: CLDR also defines 'many' for round millions / compact exponents.
    # By default require 'one' and 'other' (use --strict-romance-many to enforce 'many').
    "fr": ["one", "other"],
    "es": ["one", "other"],
    "it": ["one", "other"],
    "pt": ["one", "other"],
    # 3 forms
    "he": ["one", "two", "other"],
    "ro": ["one", "few", "other"],
    # 4 forms
    "ru": ["one", "few", "many", "other"],
    "uk": ["one", "few", "many", "other"],
    "pl": ["one", "few", "many", "other"],
    "cs": ["one", "few", "many", "other"],
    "sk": ["one", "few", "many", "other"],
    # 6 forms
    "ar": ["zero", "one", "two", "few", "many", "other"],
}

ROMANCE_MANY_LOCALES = {"fr", "es", "it", "pt"}
# CLDR locales where cardinal 'one' matches integers other than 1
# (e.g., ru/uk: 1, 21, 31, 101...; fr/hi/pt-BR/fa: 0 and 1; excludes pl where one is strictly 1).
MULTI_INTEGER_ONE_LOCALES = {
    "ru", "uk", "be", "sr", "hr", "bs", "lt", "lv", "mk", "is", "sl",
    "fr", "hi", "pt", "fa", "bn", "gu", "kn", "zu", "am", "as",
    "fil", "tl", "gd", "br",
}
ALL_CLDR_CATEGORIES = ("zero", "one", "two", "few", "many", "other")
CLDR_CATEGORY_SET = set(ALL_CLDR_CATEGORIES)
ICU_SIMPLE_TYPES = {"number", "date", "time", "spellout", "ordinal", "duration"}
ICU_COMPLEX_TYPES = {"plural", "select", "selectordinal"}

HTML_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}
NON_TRANSLATABLE_ATTRS = {"href", "class", "classname", "id", "src", "target", "rel", "to"}

# Matches HTML/JSX tags and react-i18next numeric Trans tags like <0>...</0>
HTML_TAG_RE = re.compile(
    r"<(?P<close>/?)(?P<name>[A-Za-z][A-Za-z0-9:._-]*|[0-9]+)"
    r"(?P<attrs>(?:\s+[A-Za-z_:][A-Za-z0-9:._-]*"
    r"(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|\{[^{}]*\}|[^\s\"'=<>`]+))?)*\s*)"
    r"(?P<self>/?)>"
)
ATTR_RE = re.compile(
    r"([A-Za-z_:][A-Za-z0-9:._-]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|\{([^{}]*)\}|([^\s\"'=<>`]+))"
)

I18NEXT_PH_RE = re.compile(r"\{\{\s*-?\s*([A-Za-z0-9_.-]+)(?:\s*,[^}]*)?\s*\}\}")
I18NEXT_NEST_RE = re.compile(r"\$t\(([^)]+)\)")
ICU_COMPLEX_HINT_RE = re.compile(r"\{\s*[A-Za-z0-9_]+\s*,\s*(?:plural|select|selectordinal)\s*,")
PRINTF_PH_RE = re.compile(
    r"%(?:\(([A-Za-z0-9_]+)\))?(?:([0-9]+)\$)?[#0\- +']*(?:[0-9]+|\*)?(?:\.(?:[0-9]+|\*))?(?:hh|h|ll|l|L|z|j|t)?([diuoxXfFeEgGaAcspn@%])"
)
PROP_BRACE_PH_RE = re.compile(r"\{([0-9]+|[A-Za-z_][A-Za-z0-9_.-]*)(?:\s*,[^}]*)?\}")
URL_RE = re.compile(r"https?://\S+|mailto:\S+")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def normalize_locale(locale: str) -> str:
    return re.split(r"[-_]", locale.strip())[0].lower()


def required_plural_categories(locale: str, strict_romance_many: bool = False) -> tuple[list[str], bool]:
    base = normalize_locale(locale)
    if base not in CLDR_REQUIRED_CATEGORIES:
        return ["other"], False
    cats = list(CLDR_REQUIRED_CATEGORIES[base])
    if strict_romance_many and base in ROMANCE_MANY_LOCALES and "many" not in cats:
        cats.insert(cats.index("other"), "many")
    return cats, True


def allowed_optional_categories(locale: str) -> set[str]:
    base = normalize_locale(locale)
    allowed = {"zero"}
    if base in ROMANCE_MANY_LOCALES:
        allowed.add("many")
    return allowed


def locale_one_matches_non_one(locale: str) -> bool:
    """Return True if CLDR cardinal 'one' matches integers other than 1 for this locale."""
    norm = locale.strip().replace("_", "-").lower()
    if norm == "pt-pt" or norm.startswith("pt-pt-"):
        return False
    return normalize_locale(locale) in MULTI_INTEGER_ONE_LOCALES


def has_hardcoded_digit(text: str) -> bool:
    """Return True if text contains a literal digit outside URLs, tags, and i18next placeholders."""
    cleaned = URL_RE.sub(" ", text)
    cleaned = HTML_TAG_RE.sub(" ", cleaned)
    cleaned = I18NEXT_PH_RE.sub(" ", cleaned)
    cleaned = I18NEXT_NEST_RE.sub(" ", cleaned)
    return bool(re.search(r"\d", cleaned))


def flatten_mapping(data: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten nested JSON/YAML objects into dot-delimited keys."""
    out: dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                if not v:
                    out[key] = ""
                else:
                    out.update(flatten_mapping(v, key))
            elif isinstance(v, list):
                for idx, item in enumerate(v):
                    item_key = f"{key}[{idx}]"
                    if isinstance(item, (dict, list)):
                        out.update(flatten_mapping(item, item_key))
                    else:
                        out[item_key] = item
            else:
                out[key] = v
    else:
        raise ValueError("Top-level JSON/YAML document must be an object/mapping.")
    return out


def parse_properties(path: str) -> dict[str, str]:
    """Parse a Java .properties file into key-value pairs."""
    with open(path, "r", encoding="utf-8") as fh:
        raw_lines = fh.readlines()

    logical_lines: list[str] = []
    buf = ""
    continuing = False
    for raw in raw_lines:
        line = raw.rstrip("\r\n")
        if continuing:
            line = line.lstrip(" \t\f")
        # Count trailing backslashes to detect line continuation.
        bs_count = 0
        for ch in reversed(line):
            if ch == "\\":
                bs_count += 1
            else:
                break
        if bs_count % 2 == 1:
            buf += line[:-1]
            continuing = True
        else:
            buf += line
            logical_lines.append(buf)
            buf = ""
            continuing = False
    if buf:
        logical_lines.append(buf)

    def unescape_prop(s: str) -> str:
        res: list[str] = []
        i = 0
        n = len(s)
        while i < n:
            ch = s[i]
            if ch == "\\" and i + 1 < n:
                nxt = s[i + 1]
                if nxt == "n":
                    res.append("\n")
                    i += 2
                elif nxt == "t":
                    res.append("\t")
                    i += 2
                elif nxt == "r":
                    res.append("\r")
                    i += 2
                elif nxt == "f":
                    res.append("\f")
                    i += 2
                elif nxt == "u" and i + 6 <= n:
                    hex_part = s[i + 2 : i + 6]
                    try:
                        res.append(chr(int(hex_part, 16)))
                        i += 6
                    except ValueError:
                        res.append(nxt)
                        i += 2
                else:
                    res.append(nxt)
                    i += 2
            else:
                res.append(ch)
                i += 1
        return "".join(res)

    entries: dict[str, str] = {}
    for line in logical_lines:
        stripped = line.lstrip(" \t\f")
        if not stripped or stripped[0] in ("#", "!"):
            continue
        # Find unescaped separator (=, :, or whitespace)
        sep_idx = -1
        i = 0
        while i < len(stripped):
            ch = stripped[i]
            if ch == "\\":
                i += 2
                continue
            if ch in ("=", ":", " ", "\t", "\f"):
                sep_idx = i
                break
            i += 1
        if sep_idx == -1:
            key = unescape_prop(stripped)
            val = ""
        else:
            key = unescape_prop(stripped[:sep_idx])
            rest = stripped[sep_idx:].lstrip(" \t\f")
            if rest and rest[0] in ("=", ":"):
                rest = rest[1:].lstrip(" \t\f")
            val = unescape_prop(rest)
        entries[key] = val
    return entries


def parse_po(path: str) -> tuple[dict[str, dict[str, Any]], int | None]:
    """Parse a GNU gettext .po file.

    Returns (entries_by_key, nplurals_from_header).
    Each entry is {"msgid": str, "msgid_plural": str|None, "msgstr": str|None, "msgstr_plural": dict[int, str]}.
    """
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()

    def unquote_po(quoted: str) -> str:
        s = quoted.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            s = s[1:-1]
        return (
            s.replace(r"\\", "\x00")
            .replace(r"\"", '"')
            .replace(r"\n", "\n")
            .replace(r"\t", "\t")
            .replace(r"\r", "\r")
            .replace("\x00", "\\")
        )

    entries: dict[str, dict[str, Any]] = {}
    nplurals: int | None = None

    cur: dict[str, Any] = {}
    active_field: str | None = None
    active_plural_idx: int | None = None

    def flush() -> None:
        nonlocal nplurals
        if not cur or "msgid" not in cur:
            return
        msgid = cur["msgid"]
        msgctxt = cur.get("msgctxt")
        if msgid == "" and msgctxt is None:
            header = cur.get("msgstr", "") or ""
            m = re.search(r"nplurals\s*=\s*(\d+)", header)
            if m:
                nplurals = int(m.group(1))
            return
        key = f"{msgctxt}\x04{msgid}" if msgctxt else msgid
        entries[key] = {
            "msgid": msgid,
            "msgid_plural": cur.get("msgid_plural"),
            "msgstr": cur.get("msgstr"),
            "msgstr_plural": cur.get("msgstr_plural", {}),
        }

    for raw in lines:
        line = raw.strip()
        if not line:
            flush()
            cur = {}
            active_field = None
            active_plural_idx = None
            continue
        if line.startswith("#"):
            continue
        if line.startswith("msgctxt "):
            if "msgid" in cur:
                flush()
                cur = {}
            cur["msgctxt"] = unquote_po(line[len("msgctxt ") :])
            active_field = "msgctxt"
            active_plural_idx = None
        elif line.startswith("msgid_plural "):
            cur["msgid_plural"] = unquote_po(line[len("msgid_plural ") :])
            active_field = "msgid_plural"
            active_plural_idx = None
        elif line.startswith("msgid "):
            if "msgid" in cur:
                flush()
                cur = {}
            cur["msgid"] = unquote_po(line[len("msgid ") :])
            active_field = "msgid"
            active_plural_idx = None
        elif line.startswith("msgstr["):
            m = re.match(r"msgstr\[(\d+)\]\s+(.*)", line)
            if m:
                idx = int(m.group(1))
                cur.setdefault("msgstr_plural", {})[idx] = unquote_po(m.group(2))
                active_field = "msgstr_plural"
                active_plural_idx = idx
        elif line.startswith("msgstr "):
            cur["msgstr"] = unquote_po(line[len("msgstr ") :])
            active_field = "msgstr"
            active_plural_idx = None
        elif line.startswith('"') and active_field:
            piece = unquote_po(line)
            if active_field == "msgstr_plural" and active_plural_idx is not None:
                cur["msgstr_plural"][active_plural_idx] += piece
            else:
                cur[active_field] = cur.get(active_field, "") + piece

    flush()
    return entries, nplurals


def detect_format(source_path: str, data: dict[str, Any] | None = None) -> str:
    ext = os.path.splitext(source_path)[1].lower()
    if ext == ".properties":
        return "properties"
    if ext in (".po", ".pot"):
        return "po"
    is_yaml = ext in (".yaml", ".yml")
    if data is not None:
        has_icu = any(isinstance(v, str) and ICU_COMPLEX_HINT_RE.search(v) for v in data.values())
        has_i18next = any(
            (isinstance(v, str) and I18NEXT_PH_RE.search(v))
            or split_i18next_plural(k)[1] is not None
            for k, v in data.items()
        )
        if has_icu and not has_i18next:
            return "yaml-icu" if is_yaml else "json-icu"
    return "yaml-i18next" if is_yaml else "json-i18next"


def load_structured_file(path: str, fmt: str) -> dict[str, Any]:
    if fmt.startswith("yaml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "PyYAML is required to validate YAML files. Install PyYAML or convert to JSON."
            ) from exc
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        if raw is None:
            return {}
        return flatten_mapping(raw)
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return flatten_mapping(raw)


def split_i18next_plural(key: str) -> tuple[str, str | None]:
    """Split an i18next v4 plural key into (stem, category), or (key, None)."""
    parts = key.rsplit(".", 1)
    prefix = parts[0] + "." if len(parts) == 2 else ""
    leaf = parts[-1]
    for cat in ALL_CLDR_CATEGORIES:
        suffix = f"_{cat}"
        if leaf.endswith(suffix) and len(leaf) > len(suffix):
            return prefix + leaf[: -len(suffix)], cat
    return key, None


def find_i18next_plural_families(
    src_keys: dict[str, Any], tgt_keys: dict[str, Any]
) -> dict[str, dict[str, str]]:
    """Identify i18next plural stems from source keys.

    Returns {stem: {category: full_key}}.
    """
    src_grouped: dict[str, dict[str, str]] = {}
    for k in src_keys:
        stem, cat = split_i18next_plural(k)
        if cat is not None:
            src_grouped.setdefault(stem, {})[cat] = k

    tgt_grouped: dict[str, dict[str, str]] = {}
    for k in tgt_keys:
        stem, cat = split_i18next_plural(k)
        if cat is not None:
            tgt_grouped.setdefault(stem, {})[cat] = k

    families: dict[str, dict[str, str]] = {}
    for stem, cats in src_grouped.items():
        if len(cats) >= 2:
            families[stem] = cats
        elif "other" in cats:
            val = src_keys.get(cats["other"], "")
            if (isinstance(val, str) and re.search(r"\{\{\s*-?\s*count\b", val)) or len(
                tgt_grouped.get(stem, {})
            ) >= 2:
                families[stem] = cats
    return families


# ---------------------------------------------------------------------------
# ICU MessageFormat recursive-descent parser
# ---------------------------------------------------------------------------

class ICUParseError(Exception):
    pass


class ICUBlock:
    def __init__(
        self,
        name: str,
        arg_type: str,
        selectors: list[str],
        branches: dict[str, list[ICUBlock]],
        arg_names: set[str],
    ) -> None:
        self.name = name
        self.arg_type = arg_type
        self.selectors = selectors
        self.branches = branches
        self.arg_names = arg_names


def parse_icu_message(text: str) -> tuple[set[str], list[ICUBlock]]:
    """Parse an ICU MessageFormat string.

    Returns (all_arg_names, list_of_all_complex_blocks).
    Raises ICUParseError on syntax errors.
    """
    n = len(text)
    all_args: set[str] = set()
    all_complex: list[ICUBlock] = []

    def skip_ws(pos: int) -> int:
        while pos < n and text[pos].isspace():
            pos += 1
        return pos

    def parse_message(pos: int, stop_on_close_brace: bool, in_plural: bool) -> int:
        in_quote = False
        while pos < n:
            ch = text[pos]
            if in_quote:
                if ch == "'":
                    if pos + 1 < n and text[pos + 1] == "'":
                        pos += 2
                    else:
                        in_quote = False
                        pos += 1
                else:
                    pos += 1
                continue

            if ch == "'":
                if pos + 1 < n and text[pos + 1] == "'":
                    pos += 2
                    continue
                if pos + 1 < n and (
                    text[pos + 1] in "{}" or (in_plural and text[pos + 1] == "#")
                ):
                    in_quote = True
                    pos += 2
                    continue
                pos += 1
                continue

            if ch == "}":
                if stop_on_close_brace:
                    return pos
                raise ICUParseError(f"Unmatched closing brace '}}' at position {pos}.")

            if ch == "{":
                pos = parse_argument(pos + 1)
                continue

            pos += 1

        if in_quote:
            raise ICUParseError("Unterminated single-quoted literal in ICU message.")
        if stop_on_close_brace:
            raise ICUParseError("Unclosed '{' in ICU message.")
        return pos

    def parse_argument(pos: int) -> int:
        pos = skip_ws(pos)
        start = pos
        while pos < n and text[pos] not in ",}" and not text[pos].isspace():
            if text[pos] == "{":
                raise ICUParseError(f"Unexpected '{{' inside argument name at position {pos}.")
            pos += 1
        arg_name = text[start:pos].strip()
        if not arg_name or not re.match(r"^[A-Za-z0-9_]+$", arg_name):
            raise ICUParseError(f"Invalid or empty ICU argument name at position {start}.")
        all_args.add(arg_name)

        pos = skip_ws(pos)
        if pos >= n:
            raise ICUParseError(f"Unclosed '{{' for argument '{arg_name}'.")
        if text[pos] == "}":
            return pos + 1
        if text[pos] != ",":
            raise ICUParseError(
                f"Expected ',' or '}}' after argument '{arg_name}' at position {pos}."
            )

        # Parse argType
        pos = skip_ws(pos + 1)
        t_start = pos
        while pos < n and text[pos] not in ",}" and not text[pos].isspace():
            pos += 1
        arg_type = text[t_start:pos].strip()
        if not arg_type:
            raise ICUParseError(f"Missing argument type for '{arg_name}' at position {t_start}.")

        pos = skip_ws(pos)
        if pos >= n:
            raise ICUParseError(f"Unclosed '{{' for argument '{arg_name}'.")

        if arg_type in ICU_COMPLEX_TYPES:
            if text[pos] != ",":
                raise ICUParseError(
                    f"Expected ',' after '{arg_type}' for argument '{arg_name}' at position {pos}."
                )
            pos = parse_complex_style(pos + 1, arg_name, arg_type)
            if pos >= n or text[pos] != "}":
                raise ICUParseError(
                    f"Expected '}}' closing '{arg_type}' block for '{arg_name}'."
                )
            return pos + 1

        if arg_type not in ICU_SIMPLE_TYPES:
            raise ICUParseError(
                f"Unknown ICU argument type '{arg_type}' for argument '{arg_name}'."
            )

        if text[pos] == "}":
            return pos + 1
        if text[pos] != ",":
            raise ICUParseError(
                f"Expected ',' or '}}' after type '{arg_type}' at position {pos}."
            )
        # Skip simple style until matching '}'
        pos += 1
        depth = 0
        while pos < n:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                if depth == 0:
                    return pos + 1
                depth -= 1
            pos += 1
        raise ICUParseError(f"Unclosed '{{' in style for argument '{arg_name}'.")

    def parse_complex_style(pos: int, arg_name: str, arg_type: str) -> int:
        pos = skip_ws(pos)
        # Optional offset:N for plural / selectordinal
        if arg_type in ("plural", "selectordinal") and text[pos:].startswith("offset:"):
            pos += len("offset:")
            num_start = pos
            while pos < n and text[pos].isdigit():
                pos += 1
            if pos == num_start:
                raise ICUParseError(
                    f"Invalid 'offset:' value in '{arg_type}' for '{arg_name}'."
                )
            pos = skip_ws(pos)

        selectors: list[str] = []
        while pos < n and text[pos] != "}":
            sel_start = pos
            while pos < n and text[pos] not in "{}" and not text[pos].isspace():
                pos += 1
            selector = text[sel_start:pos].strip()
            if not selector:
                raise ICUParseError(
                    f"Missing selector keyword inside '{arg_type}' for '{arg_name}' at position {sel_start}."
                )
            pos = skip_ws(pos)
            if pos >= n or text[pos] != "{":
                raise ICUParseError(
                    f"Expected '{{' after selector '{selector}' in '{arg_type}' for '{arg_name}'."
                )
            selectors.append(selector)
            pos = parse_message(pos + 1, stop_on_close_brace=True, in_plural=(arg_type != "select"))
            if pos >= n or text[pos] != "}":
                raise ICUParseError(
                    f"Unclosed '{{' in branch '{selector}' of '{arg_name}'."
                )
            pos = skip_ws(pos + 1)

        if not selectors:
            raise ICUParseError(f"Empty '{arg_type}' block for argument '{arg_name}'.")

        block = ICUBlock(
            name=arg_name,
            arg_type=arg_type,
            selectors=selectors,
            branches={},
            arg_names=set(),
        )
        all_complex.append(block)
        return pos

    parse_message(0, stop_on_close_brace=False, in_plural=False)
    return all_args, all_complex


# ---------------------------------------------------------------------------
# Placeholder & HTML tag extraction
# ---------------------------------------------------------------------------

def extract_i18next_placeholders(text: str) -> set[str]:
    phs = {m.group(1) for m in I18NEXT_PH_RE.finditer(text)}
    for m in I18NEXT_NEST_RE.finditer(text):
        phs.add(f"$t({m.group(1).strip()})")
    return phs


def extract_properties_placeholders(text: str) -> set[str]:
    phs = {m.group(1) for m in PROP_BRACE_PH_RE.finditer(text)}
    for m in PRINTF_PH_RE.finditer(text):
        if m.group(3) == "%":
            continue
        phs.add(m.group(0))
    return phs


def extract_po_placeholders(text: str) -> set[str]:
    phs: set[str] = set()
    for m in PRINTF_PH_RE.finditer(text):
        if m.group(3) == "%":
            continue
        if m.group(1):
            phs.add(f"%({m.group(1)}){m.group(3)}")
        elif m.group(2):
            phs.add(f"%{m.group(2)}${m.group(3)}")
        else:
            phs.add(f"%{m.group(3)}")
    for m in PROP_BRACE_PH_RE.finditer(text):
        phs.add(f"{{{m.group(1)}}}")
    return phs


def extract_html_tags(
    text: str,
    non_void_tags: set[str] | None = None,
) -> tuple[Counter[str], list[str]]:
    """Return (multiset of normalized tag signatures, list of balance errors)."""
    tags: Counter[str] = Counter()
    stack: list[str] = []
    balance_errors: list[str] = []
    effective_void = HTML_VOID_TAGS - non_void_tags if non_void_tags else HTML_VOID_TAGS

    for m in HTML_TAG_RE.finditer(text):
        is_close = bool(m.group("close"))
        name = m.group("name")
        attrs_raw = m.group("attrs") or ""
        is_self = bool(m.group("self")) or name.lower() in effective_void

        if is_close:
            sig = f"</{name}>"
            tags[sig] += 1
            if not stack:
                balance_errors.append(f"Unmatched closing tag '</{name}>'.")
            elif stack[-1] != name:
                if name in stack:
                    balance_errors.append(
                        f"Mismatched closing tag '</{name}>' (expected '</{stack[-1]}>')."
                    )
                    while stack and stack[-1] != name:
                        stack.pop()
                    if stack:
                        stack.pop()
                else:
                    balance_errors.append(f"Unmatched closing tag '</{name}>'.")
            else:
                stack.pop()
        else:
            kept_attrs: list[str] = []
            for am in ATTR_RE.finditer(attrs_raw):
                attr_name = am.group(1)
                attr_val = next(g for g in am.groups()[1:] if g is not None)
                if attr_name.lower() in NON_TRANSLATABLE_ATTRS:
                    kept_attrs.append(f"{attr_name}={attr_val}")
            kept_attrs.sort()
            attr_sig = (" " + " ".join(kept_attrs)) if kept_attrs else ""
            if is_self:
                tags[f"<{name}{attr_sig}/>"] += 1
            else:
                tags[f"<{name}{attr_sig}>"] += 1
                stack.append(name)

    for unclosed in stack:
        balance_errors.append(f"Unclosed opening tag '<{unclosed}>'.")
    return tags, balance_errors


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def looks_untranslated(
    src_text: str,
    tgt_text: str,
    dnt_terms: list[str],
    fmt: str,
) -> bool:
    if not src_text or src_text.strip() != tgt_text.strip():
        return False
    cleaned = src_text
    cleaned = URL_RE.sub(" ", cleaned)
    cleaned = EMAIL_RE.sub(" ", cleaned)
    cleaned = HTML_TAG_RE.sub(" ", cleaned)
    cleaned = I18NEXT_PH_RE.sub(" ", cleaned)
    cleaned = I18NEXT_NEST_RE.sub(" ", cleaned)
    if fmt.endswith("icu") or ICU_COMPLEX_HINT_RE.search(cleaned):
        cleaned = re.sub(r"\{[^{}]*\}", " ", cleaned)
    elif fmt in ("properties", "po"):
        cleaned = PROP_BRACE_PH_RE.sub(" ", cleaned)
        cleaned = PRINTF_PH_RE.sub(" ", cleaned)
    for dnt in dnt_terms:
        if dnt:
            cleaned = re.sub(re.escape(dnt), " ", cleaned)
    # Require at least one alphabetic word of length >= 2 (ignore single-letter tokens / symbols / numbers)
    return bool(re.search(r"[^\W\d_]{2,}", cleaned, re.UNICODE))


def term_present(text: str, term: str, case_sensitive: bool = False) -> bool:
    flags = 0 if case_sensitive else re.IGNORECASE
    if re.match(r"^\w.*\w$", term, re.UNICODE) or re.match(r"^\w$", term, re.UNICODE):
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
        return bool(re.search(pattern, text, flags | re.UNICODE))
    if case_sensitive:
        return term in text
    return term.lower() in text.lower()


def check_glossary_pair(
    key: str,
    src_text: str,
    tgt_text: str,
    locale: str,
    glossary: dict[str, Any],
    warnings: list[dict[str, Any]],
) -> None:
    base_locale = normalize_locale(locale)

    for dnt in glossary.get("doNotTranslate", []):
        if isinstance(dnt, str) and dnt and term_present(src_text, dnt, case_sensitive=True):
            if not term_present(tgt_text, dnt, case_sensitive=True):
                warnings.append(
                    {
                        "key": key,
                        "code": "glossary_dnt_missing",
                        "message": f"Do-not-translate term '{dnt}' appears in source but is missing in target.",
                    }
                )

    for entry in glossary.get("terms", []):
        if not isinstance(entry, dict):
            continue
        src_term = entry.get("source")
        if not isinstance(src_term, str) or not src_term:
            continue
        if not term_present(src_text, src_term, case_sensitive=False):
            continue

        translations = entry.get("translations") or {}
        expected = translations.get(locale) or translations.get(base_locale)
        if not expected:
            continue

        accepted_map = entry.get("acceptedForms") or {}
        candidates: list[str] = [expected]
        for loc_key in (locale, base_locale):
            extra = accepted_map.get(loc_key)
            if isinstance(extra, list):
                candidates.extend(x for x in extra if isinstance(x, str) and x)

        avoid_map = entry.get("avoid") or {}
        avoid_terms: list[str] = []
        for loc_key in (locale, base_locale):
            av = avoid_map.get(loc_key)
            if isinstance(av, list):
                avoid_terms.extend(x for x in av if isinstance(x, str) and x)

        tgt_lower = tgt_text.lower()
        found_avoid = [av for av in avoid_terms if av.lower() in tgt_lower]
        if found_avoid:
            warnings.append(
                {
                    "key": key,
                    "code": "glossary_avoid_term",
                    "message": (
                        f"Source contains '{src_term}' (expected '{expected}'), "
                        f"but target uses discouraged term '{found_avoid[0]}'."
                    ),
                }
            )
            continue

        if not any(cand.lower() in tgt_lower for cand in candidates):
            warnings.append(
                {
                    "key": key,
                    "code": "glossary_mismatch",
                    "message": (
                        f"Source contains glossary term '{src_term}', "
                        f"expected '{expected}' (or accepted form) in target."
                    ),
                }
            )


def check_icu_pair(
    key: str,
    src_text: str,
    tgt_text: str,
    req_cats: list[str],
    errors: list[dict[str, Any]],
    mask_i18next_double_braces: bool = False,
) -> None:
    s_in = src_text
    t_in = tgt_text
    if mask_i18next_double_braces:
        s_in = I18NEXT_PH_RE.sub("__I18NEXT_PH__", s_in)
        t_in = I18NEXT_PH_RE.sub("__I18NEXT_PH__", t_in)

    try:
        src_args, src_blocks = parse_icu_message(s_in)
    except ICUParseError as exc:
        # Source itself may contain non-ICU braces if misconfigured; still validate target.
        src_args, src_blocks = set(), []
        if ICU_COMPLEX_HINT_RE.search(s_in):
            errors.append(
                {
                    "key": key,
                    "code": "source_icu_syntax_error",
                    "message": f"Source ICU parse error: {exc}",
                }
            )

    try:
        tgt_args, tgt_blocks = parse_icu_message(t_in)
    except ICUParseError as exc:
        errors.append(
            {
                "key": key,
                "code": "icu_syntax_error",
                "message": f"Invalid ICU MessageFormat in target: {exc}",
            }
        )
        return

    if src_args != tgt_args:
        missing = sorted(src_args - tgt_args)
        extra = sorted(tgt_args - src_args)
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        errors.append(
            {
                "key": key,
                "code": "placeholder_mismatch",
                "message": f"ICU placeholder mismatch: {', '.join(parts)}.",
            }
        )

    src_select_by_name = {
        b.name: set(b.selectors) for b in src_blocks if b.arg_type == "select"
    }

    for blk in tgt_blocks:
        sel_set = set(blk.selectors)
        if "other" not in sel_set:
            errors.append(
                {
                    "key": key,
                    "code": "icu_missing_other",
                    "message": f"ICU '{blk.arg_type}' block for '{blk.name}' is missing mandatory 'other' branch.",
                }
            )

        if blk.arg_type in ("plural", "selectordinal"):
            invalid_sels = [
                s
                for s in blk.selectors
                if s not in CLDR_CATEGORY_SET and not re.match(r"^=\d+$", s)
            ]
            if invalid_sels:
                errors.append(
                    {
                        "key": key,
                        "code": "icu_invalid_selector",
                        "message": (
                            f"ICU '{blk.arg_type}' block for '{blk.name}' has invalid selector(s) "
                            f"{invalid_sels} (CLDR keywords must not be translated)."
                        ),
                    }
                )

        if blk.arg_type == "plural":
            missing_cats = [c for c in req_cats if c not in sel_set]
            if missing_cats:
                errors.append(
                    {
                        "key": key,
                        "code": "icu_missing_plural_category",
                        "message": (
                            f"ICU plural block for '{blk.name}' is missing required target-locale "
                            f"CLDR category/categories: {missing_cats}."
                        ),
                    }
                )

        if blk.arg_type == "select" and blk.name in src_select_by_name:
            expected_sels = src_select_by_name[blk.name]
            if sel_set != expected_sels:
                errors.append(
                    {
                        "key": key,
                        "code": "icu_select_mismatch",
                        "message": (
                            f"ICU select block for '{blk.name}' has selectors {sorted(sel_set)}, "
                            f"expected {sorted(expected_sels)}."
                        ),
                    }
                )


def check_html_pair(
    key: str,
    src_text: str,
    tgt_text: str,
    errors: list[dict[str, Any]],
) -> None:
    closed_in_src = {
        m.group("name").lower()
        for m in HTML_TAG_RE.finditer(src_text)
        if m.group("close")
    }
    src_tags, _ = extract_html_tags(src_text, non_void_tags=closed_in_src)
    tgt_tags, tgt_bal_errs = extract_html_tags(tgt_text, non_void_tags=closed_in_src)
    for err in tgt_bal_errs:
        errors.append(
            {
                "key": key,
                "code": "html_tag_unbalanced",
                "message": err,
            }
        )
    if src_tags != tgt_tags:
        missing = list((src_tags - tgt_tags).elements())
        extra = list((tgt_tags - src_tags).elements())
        parts: list[str] = []
        if missing:
            parts.append(f"missing {missing}")
        if extra:
            parts.append(f"unexpected {extra}")
        errors.append(
            {
                "key": key,
                "code": "html_tag_mismatch",
                "message": f"HTML/JSX tag mismatch: {', '.join(parts)}.",
            }
        )


# ---------------------------------------------------------------------------
# Main format validators
# ---------------------------------------------------------------------------

def validate_structured(
    src: dict[str, Any],
    tgt: dict[str, Any],
    locale: str,
    fmt: str,
    glossary: dict[str, Any] | None,
    strict_romance_many: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    req_cats, known_locale = required_plural_categories(locale, strict_romance_many)
    if not known_locale:
        warnings.append(
            {
                "key": "*",
                "code": "unknown_locale_plural_rules",
                "message": (
                    f"Locale '{locale}' is not in built-in CLDR table; "
                    "only enforcing 'other' plural category."
                ),
            }
        )

    is_i18next = fmt.endswith("i18next")
    is_icu = fmt.endswith("icu")
    dnt_terms = glossary.get("doNotTranslate", []) if glossary else []
    same_locale = bool(
        glossary
        and glossary.get("sourceLocale")
        and normalize_locale(str(glossary["sourceLocale"])) == normalize_locale(locale)
    )

    plural_families = find_i18next_plural_families(src, tgt) if is_i18next else {}
    src_plural_key_set = {k for cats in plural_families.values() for k in cats.values()}
    tgt_handled_keys: set[str] = set()

    # 1. Validate i18next plural families
    opt_allowed = allowed_optional_categories(locale)
    valid_tgt_cats = set(req_cats) | opt_allowed

    for stem, src_cats in sorted(plural_families.items()):
        # Check required categories in target
        present_tgt_cats: dict[str, str] = {}
        for cat in ALL_CLDR_CATEGORIES:
            candidate_key = f"{stem}_{cat}"
            if candidate_key in tgt:
                present_tgt_cats[cat] = candidate_key
                tgt_handled_keys.add(candidate_key)

        missing_cats = [c for c in req_cats if c not in present_tgt_cats]
        if missing_cats:
            errors.append(
                {
                    "key": stem,
                    "code": "missing_plural_category",
                    "message": (
                        f"Plural family '{stem}' is missing required category/categories "
                        f"for locale '{locale}': {missing_cats} "
                        f"(expected keys: {[f'{stem}_{c}' for c in missing_cats]})."
                    ),
                }
            )

        unexpected_cats = [c for c in present_tgt_cats if c not in valid_tgt_cats]
        for ucat in unexpected_cats:
            warnings.append(
                {
                    "key": present_tgt_cats[ucat],
                    "code": "extra_plural_category",
                    "message": (
                        f"Plural category '{ucat}' is not required for locale '{locale}'."
                    ),
                }
            )

        # Compute source placeholder union and representative source string
        src_vals = [str(src[k]) for k in src_cats.values() if isinstance(src[k], str)]
        src_ph_union: set[str] = set()
        for sv in src_vals:
            src_ph_union |= extract_i18next_placeholders(sv)
        non_count_phs = {p for p in src_ph_union if p != "count"}
        rep_src = str(src[src_cats.get("other") or next(iter(src_cats.values()))])

        for cat, tkey in sorted(present_tgt_cats.items()):
            tval = tgt[tkey]
            if not isinstance(tval, str):
                errors.append(
                    {
                        "key": tkey,
                        "code": "type_mismatch",
                        "message": f"Expected string value for '{tkey}', got {type(tval).__name__}.",
                    }
                )
                continue

            t_phs = extract_i18next_placeholders(tval)
            invented = sorted(t_phs - src_ph_union)
            missing_non_count = sorted(non_count_phs - t_phs)
            if invented or missing_non_count:
                parts = []
                if missing_non_count:
                    parts.append(f"missing {missing_non_count}")
                if invented:
                    parts.append(f"unexpected {invented}")
                errors.append(
                    {
                        "key": tkey,
                        "code": "placeholder_mismatch",
                        "message": f"Placeholder mismatch: {', '.join(parts)}.",
                    }
                )
            if "count" in src_ph_union and cat in ("other", "few", "many") and "count" not in t_phs:
                errors.append(
                    {
                        "key": tkey,
                        "code": "placeholder_mismatch",
                        "message": "Placeholder mismatch: missing ['count'] in plural form.",
                    }
                )
            if cat == "one" and locale_one_matches_non_one(locale):
                missing_count = "count" in src_ph_union and "count" not in t_phs
                hardcoded_digit = has_hardcoded_digit(tval)
                if missing_count or hardcoded_digit:
                    reasons: list[str] = []
                    if missing_count:
                        reasons.append("missing 'count' placeholder")
                    if hardcoded_digit:
                        reasons.append("contains a hard-coded digit")
                    warnings.append(
                        {
                            "key": tkey,
                            "code": "plural_hardcoded_one",
                            "message": (
                                f"Plural 'one' form for locale '{locale}' matches values other than 1 "
                                f"({', '.join(reasons)}); keep the count placeholder instead of hard-coding 1."
                            ),
                        }
                    )

            check_html_pair(tkey, rep_src, tval, errors)
            if glossary:
                check_glossary_pair(tkey, rep_src, tval, locale, glossary, warnings)
            if not same_locale and looks_untranslated(rep_src, tval, dnt_terms, fmt):
                warnings.append(
                    {
                        "key": tkey,
                        "code": "untranslated_value",
                        "message": "Target value is identical to source.",
                    }
                )

    # 2. Validate regular (non-plural-family) keys
    for key, sval in src.items():
        if key in src_plural_key_set:
            continue
        if key not in tgt:
            errors.append(
                {
                    "key": key,
                    "code": "missing_key",
                    "message": f"Key '{key}' is present in source but missing in target.",
                }
            )
            continue

        tgt_handled_keys.add(key)
        tval = tgt[key]
        if type(sval) is not type(tval):
            errors.append(
                {
                    "key": key,
                    "code": "type_mismatch",
                    "message": f"Type mismatch: source is {type(sval).__name__}, target is {type(tval).__name__}.",
                }
            )
            continue
        if not isinstance(sval, str) or not isinstance(tval, str):
            continue

        # Placeholder & ICU checks
        if is_icu:
            check_icu_pair(key, sval, tval, req_cats, errors, mask_i18next_double_braces=False)
        elif is_i18next:
            s_phs = extract_i18next_placeholders(sval)
            t_phs = extract_i18next_placeholders(tval)
            if s_phs != t_phs:
                missing = sorted(s_phs - t_phs)
                extra = sorted(t_phs - s_phs)
                parts = []
                if missing:
                    parts.append(f"missing {missing}")
                if extra:
                    parts.append(f"unexpected {extra}")
                errors.append(
                    {
                        "key": key,
                        "code": "placeholder_mismatch",
                        "message": f"Placeholder mismatch: {', '.join(parts)}.",
                    }
                )
            # Also check embedded ICU syntax (or stray single braces) if present
            s_masked = I18NEXT_PH_RE.sub("__I18NEXT_PH__", sval)
            t_masked = I18NEXT_PH_RE.sub("__I18NEXT_PH__", tval)
            if "{" in s_masked or "}" in s_masked or "{" in t_masked or "}" in t_masked:
                check_icu_pair(key, sval, tval, req_cats, errors, mask_i18next_double_braces=True)
        elif fmt == "properties":
            if ICU_COMPLEX_HINT_RE.search(sval) or ICU_COMPLEX_HINT_RE.search(tval):
                check_icu_pair(key, sval, tval, req_cats, errors, mask_i18next_double_braces=False)
            else:
                s_phs = extract_properties_placeholders(sval)
                t_phs = extract_properties_placeholders(tval)
                if s_phs != t_phs:
                    missing = sorted(s_phs - t_phs)
                    extra = sorted(t_phs - s_phs)
                    parts = []
                    if missing:
                        parts.append(f"missing {missing}")
                    if extra:
                        parts.append(f"unexpected {extra}")
                    errors.append(
                        {
                            "key": key,
                            "code": "placeholder_mismatch",
                            "message": f"Placeholder mismatch: {', '.join(parts)}.",
                        }
                    )

        # HTML/JSX tag check
        check_html_pair(key, sval, tval, errors)

        # Untranslated value warning
        if not same_locale and looks_untranslated(sval, tval, dnt_terms, fmt):
            warnings.append(
                {
                    "key": key,
                    "code": "untranslated_value",
                    "message": "Target value is identical to source.",
                }
            )

        # Glossary check
        if glossary:
            check_glossary_pair(key, sval, tval, locale, glossary, warnings)

    # 3. Extra keys in target (report as warning, never auto-delete)
    for key in sorted(tgt.keys()):
        if key not in tgt_handled_keys:
            warnings.append(
                {
                    "key": key,
                    "code": "extra_key",
                    "message": f"Key '{key}' exists in target but not in source.",
                }
            )

    return errors, warnings


def validate_po_files(
    src_path: str,
    tgt_path: str,
    locale: str,
    glossary: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    src_entries, _ = parse_po(src_path)
    tgt_entries, tgt_nplurals = parse_po(tgt_path)
    dnt_terms = glossary.get("doNotTranslate", []) if glossary else []
    same_locale = bool(
        glossary
        and glossary.get("sourceLocale")
        and normalize_locale(str(glossary["sourceLocale"])) == normalize_locale(locale)
    )

    for key, sentry in src_entries.items():
        if key not in tgt_entries:
            errors.append(
                {
                    "key": key,
                    "code": "missing_key",
                    "message": f"Message '{key}' is missing in target .po file.",
                }
            )
            continue

        tentry = tgt_entries[key]
        if sentry["msgid_plural"] is not None:
            t_plurals: dict[int, str] = tentry.get("msgstr_plural") or {}
            expected_n = tgt_nplurals or max(len(t_plurals), 2)
            for idx in range(expected_n):
                if idx not in t_plurals or not t_plurals[idx].strip():
                    errors.append(
                        {
                            "key": f"{key}[{idx}]",
                            "code": "missing_plural_category",
                            "message": f"Missing or empty msgstr[{idx}] for plural entry '{key}'.",
                        }
                    )
            src_phs = extract_po_placeholders(sentry["msgid"]) | extract_po_placeholders(
                sentry["msgid_plural"]
            )
            for idx, tval in sorted(t_plurals.items()):
                if not tval.strip():
                    continue
                t_phs = extract_po_placeholders(tval)
                if t_phs != src_phs:
                    errors.append(
                        {
                            "key": f"{key}[{idx}]",
                            "code": "placeholder_mismatch",
                            "message": f"Placeholder mismatch: expected {sorted(src_phs)}, got {sorted(t_phs)}.",
                        }
                    )
                check_html_pair(f"{key}[{idx}]", sentry["msgid_plural"], tval, errors)
                if glossary:
                    check_glossary_pair(f"{key}[{idx}]", sentry["msgid_plural"], tval, locale, glossary, warnings)
        else:
            src_text = sentry["msgstr"] or sentry["msgid"]
            tgt_text = tentry.get("msgstr") or ""
            if not tgt_text.strip():
                errors.append(
                    {
                        "key": key,
                        "code": "missing_key",
                        "message": f"Empty msgstr for '{key}'.",
                    }
                )
                continue
            s_phs = extract_po_placeholders(src_text)
            t_phs = extract_po_placeholders(tgt_text)
            if s_phs != t_phs:
                errors.append(
                    {
                        "key": key,
                        "code": "placeholder_mismatch",
                        "message": f"Placeholder mismatch: expected {sorted(s_phs)}, got {sorted(t_phs)}.",
                    }
                )
            check_html_pair(key, src_text, tgt_text, errors)
            if not same_locale and looks_untranslated(src_text, tgt_text, dnt_terms, "po"):
                warnings.append(
                    {
                        "key": key,
                        "code": "untranslated_value",
                        "message": "Target value is identical to source.",
                    }
                )
            if glossary:
                check_glossary_pair(key, src_text, tgt_text, locale, glossary, warnings)

    for key in sorted(tgt_entries.keys()):
        if key not in src_entries:
            warnings.append(
                {
                    "key": key,
                    "code": "extra_key",
                    "message": f"Message '{key}' exists in target .po file but not in source.",
                }
            )

    return errors, warnings


def format_human_report(report: dict[str, Any]) -> str:
    lines = [
        f"Validation {report['status'].upper()} | locale={report['locale']} | format={report['format']}",
        f"Errors: {report['error_count']} | Warnings: {report['warning_count']}",
    ]
    if report["errors"]:
        lines.append("\nERRORS:")
        for item in report["errors"]:
            lines.append(f"  - [{item['code']}] {item['key']}: {item['message']}")
    if report["warnings"]:
        lines.append("\nWARNINGS:")
        for item in report["warnings"]:
            lines.append(f"  - [{item['code']}] {item['key']}: {item['message']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Validate a translated i18n file against its source file."
    )
    parser.add_argument("source", help="Path to source locale file")
    parser.add_argument("target", help="Path to target locale file")
    parser.add_argument(
        "--locale",
        required=True,
        help="Target BCP 47 locale code (e.g., ru, ru-RU, ar, ja, tr)",
    )
    parser.add_argument(
        "--format",
        dest="fmt",
        default="auto",
        choices=["auto", "json-i18next", "json-icu", "yaml-i18next", "yaml-icu", "properties", "po"],
        help="File format (default: auto)",
    )
    parser.add_argument(
        "--glossary",
        help="Optional path to i18n-glossary.json",
    )
    parser.add_argument(
        "--strict-romance-many",
        action="store_true",
        help="Require CLDR 'many' category for fr/es/it/pt (for compact/million counters)",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Output machine-readable JSON",
    )
    args = parser.parse_args(argv)

    glossary: dict[str, Any] | None = None
    if args.glossary:
        try:
            with open(args.glossary, "r", encoding="utf-8") as fh:
                glossary = json.load(fh)
        except Exception as exc:
            err = f"Failed to load glossary '{args.glossary}': {exc}"
            if args.as_json:
                print(json.dumps({"status": "fail", "error_count": 1, "warning_count": 0, "errors": [{"key": "*", "code": "glossary_load_error", "message": err}], "warnings": []}, ensure_ascii=False, indent=2))
            else:
                print(f"ERROR: {err}", file=sys.stderr)
            return 1

    fmt = args.fmt
    try:
        if fmt == "po" or (fmt == "auto" and os.path.splitext(args.source)[1].lower() in (".po", ".pot")):
            fmt = "po"
            errors, warnings = validate_po_files(args.source, args.target, args.locale, glossary)
        elif fmt == "properties" or (
            fmt == "auto" and os.path.splitext(args.source)[1].lower() == ".properties"
        ):
            fmt = "properties"
            src_data = parse_properties(args.source)
            tgt_data = parse_properties(args.target)
            errors, warnings = validate_structured(
                src_data, tgt_data, args.locale, fmt, glossary, args.strict_romance_many
            )
        else:
            initial_fmt = fmt if fmt != "auto" else detect_format(args.source)
            src_data = load_structured_file(args.source, initial_fmt)
            if fmt == "auto":
                fmt = detect_format(args.source, src_data)
            tgt_data = load_structured_file(args.target, fmt)
            errors, warnings = validate_structured(
                src_data, tgt_data, args.locale, fmt, glossary, args.strict_romance_many
            )
    except Exception as exc:
        report = {
            "status": "fail",
            "locale": args.locale,
            "format": fmt,
            "error_count": 1,
            "warning_count": 0,
            "errors": [{"key": "*", "code": "parse_error", "message": str(exc)}],
            "warnings": [],
        }
        if args.as_json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_human_report(report))
        return 1

    report = {
        "status": "pass" if not errors else "fail",
        "locale": args.locale,
        "format": fmt,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors,
        "warnings": warnings,
    }
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_human_report(report))

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
