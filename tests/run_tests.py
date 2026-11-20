#!/usr/bin/env python3
"""Test suite for scripts/validate_i18n.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "validate_i18n.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")


def _utf8_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_validator(args: list[str]) -> tuple[int, dict, str]:
    cmd = [sys.executable, SCRIPT, *args, "--json"]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_utf8_env(),
        check=False,
    )
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Validator did not emit valid JSON.\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        ) from exc
    return proc.returncode, data, proc.stderr


class ValidateI18nTests(unittest.TestCase):
    def test_valid_russian_i18next_passes_cleanly(self) -> None:
        rc, report, _ = run_validator(
            [
                os.path.join(FIXTURES, "en_i18next.json"),
                os.path.join(FIXTURES, "ru_i18next_valid.json"),
                "--locale",
                "ru",
                "--format",
                "json-i18next",
                "--glossary",
                os.path.join(FIXTURES, "i18n-glossary.json"),
            ]
        )
        self.assertEqual(rc, 0, msg=report)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["error_count"], 0, msg=report["errors"])
        self.assertEqual(report["warning_count"], 0, msg=report["warnings"])

    def test_broken_russian_i18next_catches_all_defects(self) -> None:
        rc, report, _ = run_validator(
            [
                os.path.join(FIXTURES, "en_i18next.json"),
                os.path.join(FIXTURES, "ru_i18next_broken.json"),
                "--locale",
                "ru",
                "--format",
                "json-i18next",
                "--glossary",
                os.path.join(FIXTURES, "i18n-glossary.json"),
            ]
        )
        self.assertEqual(rc, 1, msg=report)
        self.assertEqual(report["status"], "fail")

        err_pairs = {(e["code"], e["key"]) for e in report["errors"]}
        warn_pairs = {(w["code"], w["key"]) for w in report["warnings"]}

        # Required error detections:
        self.assertIn(("missing_key", "actions.delete"), err_pairs)
        self.assertIn(("placeholder_mismatch", "greeting"), err_pairs)
        self.assertIn(("html_tag_mismatch", "terms_notice"), err_pairs)
        self.assertIn(("missing_plural_category", "cart.items"), err_pairs)
        self.assertIn(("icu_syntax_error", "notifications.invite_summary"), err_pairs)

        # Required warning detections:
        self.assertIn(("extra_key", "actions.legacy_unused"), warn_pairs)
        self.assertIn(("untranslated_value", "actions.save"), warn_pairs)
        self.assertIn(("glossary_dnt_missing", "brand"), warn_pairs)
        self.assertIn(("glossary_avoid_term", "nav.workspace"), warn_pairs)
        self.assertIn(("glossary_mismatch", "nav.billing"), warn_pairs)

    def test_warnings_only_exits_zero(self) -> None:
        rc, report, _ = run_validator(
            [
                os.path.join(FIXTURES, "en_i18next.json"),
                os.path.join(FIXTURES, "ru_i18next_warnings_only.json"),
                "--locale",
                "ru",
                "--format",
                "json-i18next",
                "--glossary",
                os.path.join(FIXTURES, "i18n-glossary.json"),
            ]
        )
        self.assertEqual(rc, 0, msg=report)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["error_count"], 0)
        self.assertGreaterEqual(report["warning_count"], 3)

    def test_arabic_icu_valid_and_broken(self) -> None:
        rc_ok, rep_ok, _ = run_validator(
            [
                os.path.join(FIXTURES, "en_icu.json"),
                os.path.join(FIXTURES, "ar_icu_valid.json"),
                "--locale",
                "ar",
                "--format",
                "json-icu",
            ]
        )
        self.assertEqual(rc_ok, 0, msg=rep_ok)
        self.assertEqual(rep_ok["error_count"], 0)

        rc_bad, rep_bad, _ = run_validator(
            [
                os.path.join(FIXTURES, "en_icu.json"),
                os.path.join(FIXTURES, "ar_icu_broken.json"),
                "--locale",
                "ar",
                "--format",
                "json-icu",
            ]
        )
        self.assertEqual(rc_bad, 1, msg=rep_bad)
        err_pairs = {(e["code"], e["key"]) for e in rep_bad["errors"]}
        self.assertIn(("icu_missing_plural_category", "files_count"), err_pairs)
        self.assertIn(("icu_missing_other", "role_label"), err_pairs)
        self.assertIn(("icu_select_mismatch", "role_label"), err_pairs)

    def test_properties_valid_and_broken(self) -> None:
        rc_ok, rep_ok, _ = run_validator(
            [
                os.path.join(FIXTURES, "en.properties"),
                os.path.join(FIXTURES, "tr_valid.properties"),
                "--locale",
                "tr",
                "--format",
                "properties",
                "--glossary",
                os.path.join(FIXTURES, "i18n-glossary.json"),
            ]
        )
        self.assertEqual(rc_ok, 0, msg=rep_ok)
        self.assertEqual(rep_ok["error_count"], 0)
        self.assertEqual(rep_ok["warning_count"], 0)

        rc_bad, rep_bad, _ = run_validator(
            [
                os.path.join(FIXTURES, "en.properties"),
                os.path.join(FIXTURES, "tr_broken.properties"),
                "--locale",
                "tr",
                "--format",
                "properties",
            ]
        )
        self.assertEqual(rc_bad, 1, msg=rep_bad)
        err_pairs = {(e["code"], e["key"]) for e in rep_bad["errors"]}
        self.assertIn(("placeholder_mismatch", "app.welcome"), err_pairs)
        self.assertIn(("missing_key", "app.workspace.delete"), err_pairs)

    def test_po_valid_and_broken(self) -> None:
        rc_ok, rep_ok, _ = run_validator(
            [
                os.path.join(FIXTURES, "en.po"),
                os.path.join(FIXTURES, "ru_valid.po"),
                "--locale",
                "ru",
                "--format",
                "po",
            ]
        )
        self.assertEqual(rc_ok, 0, msg=rep_ok)
        self.assertEqual(rep_ok["error_count"], 0)

        rc_bad, rep_bad, _ = run_validator(
            [
                os.path.join(FIXTURES, "en.po"),
                os.path.join(FIXTURES, "ru_broken.po"),
                "--locale",
                "ru",
                "--format",
                "po",
            ]
        )
        self.assertEqual(rc_bad, 1, msg=rep_bad)
        err_pairs = {(e["code"], e["key"]) for e in rep_bad["errors"]}
        self.assertIn(("placeholder_mismatch", "Hello, %s!"), err_pairs)
        self.assertIn(("missing_plural_category", "%d file[2]"), err_pairs)

    def test_human_readable_output(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                os.path.join(FIXTURES, "en_i18next.json"),
                os.path.join(FIXTURES, "ru_i18next_valid.json"),
                "--locale",
                "ru",
                "--format",
                "json-i18next",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_utf8_env(),
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Validation PASS", proc.stdout)

    def test_icu_rich_text_link_tag_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, "en.json")
            tgt_ok_path = os.path.join(tmpdir, "tr_ok.json")
            tgt_bad_path = os.path.join(tmpdir, "tr_bad.json")
            with open(src_path, "w", encoding="utf-8") as fh:
                json.dump({"notice": "Read <link>x</link> before continuing."}, fh, ensure_ascii=False)
            with open(tgt_ok_path, "w", encoding="utf-8") as fh:
                json.dump({"notice": "Devam etmeden önce <link>x</link> metnini okuyun."}, fh, ensure_ascii=False)
            with open(tgt_bad_path, "w", encoding="utf-8") as fh:
                json.dump({"notice": "Devam etmeden önce <link>x metnini okuyun."}, fh, ensure_ascii=False)

            rc_ok, rep_ok, _ = run_validator(
                [src_path, tgt_ok_path, "--locale", "tr", "--format", "json-icu"]
            )
            self.assertEqual(rc_ok, 0, msg=rep_ok)
            self.assertEqual(rep_ok["error_count"], 0, msg=rep_ok["errors"])

            rc_bad, rep_bad, _ = run_validator(
                [src_path, tgt_bad_path, "--locale", "tr", "--format", "json-icu"]
            )
            self.assertEqual(rc_bad, 1, msg=rep_bad)
            err_codes = {e["code"] for e in rep_bad["errors"]}
            self.assertIn("html_tag_unbalanced", err_codes)

    def test_plural_hardcoded_one_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            src_path = os.path.join(tmpdir, "en.json")
            ru_warn_path = os.path.join(tmpdir, "ru_warn.json")
            ru_digit_path = os.path.join(tmpdir, "ru_digit.json")
            pl_ok_path = os.path.join(tmpdir, "pl_ok.json")

            with open(src_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "items_one": "1 item",
                        "items_other": "{{count}} items",
                    },
                    fh,
                    ensure_ascii=False,
                )
            # Russian 'one' matches 1, 21, 31...: omitting {{count}} should warn.
            with open(ru_warn_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "items_one": "Один элемент",
                        "items_few": "{{count}} элемента",
                        "items_many": "{{count}} элементов",
                        "items_other": "{{count}} элемента",
                    },
                    fh,
                    ensure_ascii=False,
                )
            # Russian 'one' with a hard-coded digit should also warn.
            with open(ru_digit_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "items_one": "1 элемент ({{count}})",
                        "items_few": "{{count}} элемента",
                        "items_many": "{{count}} элементов",
                        "items_other": "{{count}} элемента",
                    },
                    fh,
                    ensure_ascii=False,
                )
            # Polish 'one' only matches n=1 in CLDR: hard-coded '1' should NOT warn.
            with open(pl_ok_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "items_one": "1 element",
                        "items_few": "{{count}} elementy",
                        "items_many": "{{count}} elementów",
                        "items_other": "{{count}} elementu",
                    },
                    fh,
                    ensure_ascii=False,
                )

            rc_ru, rep_ru, _ = run_validator(
                [src_path, ru_warn_path, "--locale", "ru", "--format", "json-i18next"]
            )
            self.assertEqual(rc_ru, 0, msg=rep_ru)
            self.assertIn(
                ("plural_hardcoded_one", "items_one"),
                {(w["code"], w["key"]) for w in rep_ru["warnings"]},
            )

            rc_ru_d, rep_ru_d, _ = run_validator(
                [src_path, ru_digit_path, "--locale", "ru", "--format", "json-i18next"]
            )
            self.assertEqual(rc_ru_d, 0, msg=rep_ru_d)
            self.assertIn(
                ("plural_hardcoded_one", "items_one"),
                {(w["code"], w["key"]) for w in rep_ru_d["warnings"]},
            )

            rc_pl, rep_pl, _ = run_validator(
                [src_path, pl_ok_path, "--locale", "pl", "--format", "json-i18next"]
            )
            self.assertEqual(rc_pl, 0, msg=rep_pl)
            self.assertNotIn(
                "plural_hardcoded_one",
                {w["code"] for w in rep_pl["warnings"]},
            )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ValidateI18nTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
