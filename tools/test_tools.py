"""Tests for the catalog build and the Windows scan helpers.

Plain `unittest`, no fixtures or third-party packages. Run from the repo root:

    python -m unittest discover -s tools -p "test_*.py"

Everything here is pure logic, so it runs on any OS (the Windows scan imports
`winreg` lazily for exactly this reason).
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_catalog as bc  # noqa: E402
import scan_system_apps_windows as sw  # noqa: E402


class NormalizeName(unittest.TestCase):
    def test_vendor_and_edition_noise_is_dropped(self):
        self.assertEqual(
            bc.normalize_name("Microsoft Visual Studio Code (User)"),
            bc.normalize_name("Visual Studio Code"),
        )

    def test_trailing_year_is_dropped(self):
        self.assertEqual(
            bc.normalize_name("Visual Studio Community 2022"),
            bc.normalize_name("Visual Studio"),
        )

    def test_a_name_that_is_a_number_survives(self):
        self.assertEqual(bc.normalize_name("2048"), "2048")

    def test_a_glued_trailing_app_is_dropped_but_short_names_are_not(self):
        self.assertEqual(bc.normalize_name("ResponsivelyApp"), bc.normalize_name("Responsively App"))
        self.assertEqual(bc.normalize_name("Snapp"), "snapp")

    def test_locale_tags_are_dropped(self):
        self.assertEqual(bc.normalize_name("Foo en-US"), bc.normalize_name("Foo"))


class GuessBins(unittest.TestCase):
    def test_windows_guess_needs_winget_and_a_plain_executable_name(self):
        self.assertEqual(bc.guess_windows_bin({"windows_winget": "x"}, "git"), "git.exe")
        # A package id is not an executable name: present but empty, so the app
        # is still known to exist on Windows and can be found by name.
        self.assertEqual(bc.guess_windows_bin({"windows_winget": "x"}, "dbeaver-ce"), "")
        # No winget id: not a Windows app, the slot stays absent.
        self.assertIsNone(bc.guess_windows_bin({}, "git"))
        self.assertNotIn("windows", bc.build_bin({}, "git", "git"))
        self.assertEqual(bc.build_bin({"windows_winget": "x"}, "dbeaver-ce", "dbeaver")["windows"], "")

    def test_macos_guess_title_cases_the_brew_slug(self):
        self.assertEqual(
            bc.guess_macos_bin({"macos_brew": "visual-studio-code"}), "Visual Studio Code"
        )
        self.assertIsNone(bc.guess_macos_bin({}))

    def test_overrides_win_over_guesses(self):
        out = bc.build_bin({"windows_winget": "x"}, "code", "visual-studio-code")
        self.assertEqual(out["windows"], "Code.exe")


class MergeWindowsScan(unittest.TestCase):
    def setUp(self):
        self.curated = {
            "id": "gimp",
            "name": "GIMP",
            "vendor": "",
            "category": "Graphics",
            "bin": {"linux": "gimp"},
            "icon": "gimp.png",
            "hidden": False,
            "cli": False,
        }
        self.by_bin = {"gimp": self.curated}

    def scan(self, **kw):
        entry = {"id": "win-gimp", "name": "GIMP 3.0.4 (x64)", "bin": r"C:\GIMP\gimp.exe",
                 "category": "Utilities"}
        entry.update(kw)
        return entry

    def test_matches_curated_entry_by_name_and_keeps_its_name_and_category(self):
        new = bc.merge_system_scan(self.by_bin, [self.scan(name="GIMP")], "windows")
        self.assertEqual(new, 0)
        self.assertEqual(self.curated["bin"]["windows"], r"C:\GIMP\gimp.exe")
        self.assertEqual(self.curated["bin"]["linux"], "gimp")  # other OS slot preserved
        self.assertEqual(self.curated["category"], "Graphics")
        self.assertEqual(self.curated["name"], "GIMP")

    def test_matches_by_executable_basename(self):
        self.curated["bin"]["windows"] = "gimp.exe"
        new = bc.merge_system_scan(self.by_bin, [self.scan(name="Something Else")], "windows")
        self.assertEqual(new, 0)
        self.assertEqual(self.curated["bin"]["windows"], r"C:\GIMP\gimp.exe")

    def test_unmatched_app_becomes_a_new_entry(self):
        new = bc.merge_system_scan(
            self.by_bin,
            [self.scan(id="win-foo", name="Foo", bin=r"C:\Foo\foo.exe", category="Office")],
            "windows",
        )
        self.assertEqual(new, 1)
        added = self.by_bin[r"C:\Foo\foo.exe"]
        self.assertEqual((added["id"], added["category"]), ("win-foo", "Office"))

    def test_excluded_ids_are_skipped(self):
        excluded = next(iter(bc.EXCLUDED_IDS))
        new = bc.merge_system_scan(self.by_bin, [self.scan(id=excluded)], "windows")
        self.assertEqual(new, 0)
        self.assertNotIn("windows", self.curated["bin"])

    def test_cli_flag_is_never_cleared_by_a_scan(self):
        self.curated["cli"] = True
        bc.merge_system_scan(self.by_bin, [self.scan(name="GIMP")], "windows")
        self.assertTrue(self.curated["cli"])


class PlaceScanIcons(unittest.TestCase):
    def test_places_staged_icons_and_prunes_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            icons, cache = Path(tmp, "icons"), Path(tmp, "cache")
            icons.mkdir()
            cache.mkdir()
            (cache / "staged.png").write_bytes(b"new")
            (icons / "orphan.png").write_bytes(b"old")
            (icons / "kept.png").write_bytes(b"keep")
            (icons / "category").mkdir()  # fallback glyphs live here; never pruned
            entries = [
                {"id": "a", "icon": "a.png", "_scan_icon": "staged.png"},
                {"id": "kept", "icon": "kept.png"},
            ]
            with mock.patch.object(bc, "ICONS_DIR", icons), mock.patch.object(bc, "ICON_CACHE", cache):
                placed, pruned = bc.place_scan_icons(entries)
            self.assertEqual((placed, pruned), (1, 1))
            self.assertEqual((icons / "a.png").read_bytes(), b"new")
            self.assertFalse((icons / "orphan.png").exists())
            self.assertTrue((icons / "kept.png").exists())
            self.assertTrue((icons / "category").is_dir())
            self.assertNotIn("_scan_icon", entries[0])


class ScanHelpers(unittest.TestCase):
    def test_clean_name_strips_version_and_arch_noise(self):
        self.assertEqual(sw.clean_name("7-Zip 26.03 (x64)"), "7-Zip")
        self.assertEqual(sw.clean_name("Golden Cheetah v3.8 (64bit)"), "Golden Cheetah")
        # A bare year is part of the product name.
        self.assertEqual(sw.clean_name("Microsoft Office Home 2024"), "Microsoft Office Home 2024")

    def test_clean_name_strips_install_scope_and_taglines(self):
        self.assertEqual(sw.clean_name("WinMerge x64 (Current user, 64-bit)"), "WinMerge")
        self.assertEqual(sw.clean_name("Tesseract-OCR - open source OCR engine"), "Tesseract-OCR")
        # A dash followed by a version is left for the version patterns, and a
        # dangling dash must not survive them.
        self.assertEqual(sw.clean_name("Foo Runtime - 1.2.3"), "Foo Runtime")

    def test_clean_name_drops_release_channel_tags(self):
        self.assertEqual(sw.clean_name("PowerToys (Preview) x64"), "PowerToys")
        self.assertEqual(sw.clean_name("Foo (Beta)"), "Foo")
        # A parenthesised part that is not a channel tag stays.
        self.assertEqual(sw.clean_name("Lucas Chess (R)"), "Lucas Chess (R)")

    def test_guess_category_covers_dev_tools_named_without_word_breaks(self):
        self.assertEqual(sw.guess_category("ResponsivelyApp"), "Development")
        self.assertEqual(sw.guess_category("Inno Setup"), "Development")
        self.assertEqual(sw.guess_category("Some Unknown Thing"), "Utilities")

    def test_runtimes_and_updates_are_not_apps(self):
        self.assertTrue(sw.is_non_app("OpenAL"))
        self.assertTrue(sw.is_non_app("Microsoft .NET Runtime - 10.0.12 (x64)"))
        self.assertTrue(sw.is_non_app("Microsoft Visual C++ 2015-2022 Redistributable"))
        self.assertFalse(sw.is_non_app("Visual Studio Code"))

    def test_extract_exe_path_strips_resource_index_and_rejects_non_exe(self):
        self.assertEqual(sw.extract_exe_path(r'"C:\A\a.exe",0'), r"C:\A\a.exe")
        self.assertEqual(sw.extract_exe_path(r"C:\A\a.exe,-101"), r"C:\A\a.exe")
        self.assertIsNone(sw.extract_exe_path(r"C:\A\a.ico"))

    def test_collapse_env_only_rewrites_per_user_prefixes(self):
        env = {"LOCALAPPDATA": r"C:\Users\me\AppData\Local", "APPDATA": r"C:\Users\me\AppData\Roaming",
               "USERPROFILE": r"C:\Users\me"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(
                sw.collapse_env(r"C:\Users\me\AppData\Local\Programs\X\x.exe"),
                r"%LOCALAPPDATA%\Programs\X\x.exe",
            )
            self.assertEqual(sw.collapse_env(r"c:\users\ME\.bun\bin\bun.exe"), r"%USERPROFILE%\.bun\bin\bun.exe")
            self.assertEqual(sw.collapse_env(r"C:\Program Files\X\x.exe"), r"C:\Program Files\X\x.exe")

    def test_installer_executables_are_recognised(self):
        for bad in (r"C:\Steam\uninstall.exe", r"C:\O\unins000.exe", r"C:\C\uninst.exe",
                    r"C:\Users\me\AppData\Local\Package Cache\{guid}\python-3.13-amd64.exe",
                    r"C:\X\FooSetup.exe"):
            self.assertTrue(sw.is_installer_exe(bad), bad)
        for good in (r"C:\Steam\steam.exe", r"C:\Program Files\Inno Setup 7\ISIDE.exe"):
            self.assertFalse(sw.is_installer_exe(good), good)

    def test_find_real_exe_skips_installers_and_needs_a_name_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("uninstall.exe", "steamwebhelper_setup.exe", "Steam.exe", "other.exe"):
                Path(tmp, name).write_bytes(b"")
            found = sw.find_real_exe([tmp], "Steam")
            self.assertEqual(Path(found).name, "Steam.exe")
            self.assertIsNone(sw.find_real_exe([tmp], "Unrelated App"))
            # An exact name beats an alphabetically earlier prefix match.
            for name in ("PowerToys.ActionRunner.exe", "PowerToys.exe"):
                Path(tmp, name).write_bytes(b"")
            self.assertEqual(Path(sw.find_real_exe([tmp], "PowerToys")).name, "PowerToys.exe")
            self.assertIsNone(sw.find_real_exe(["", str(Path(tmp, "missing"))], "Steam"))


class CatalogIntegrity(unittest.TestCase):
    """The committed catalog must satisfy the invariants SPEC.md promises."""

    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(bc.OUT.read_text(encoding="utf-8"))

    def test_ids_are_unique_and_categories_valid(self):
        ids = [e["id"] for e in self.catalog]
        self.assertEqual(len(ids), len(set(ids)))
        valid = {"Development", "Education", "Graphics", "Internet", "Games",
                 "Multimedia", "Office", "Science", "System", "Utilities"}
        self.assertFalse([e["id"] for e in self.catalog if e["category"] not in valid])

    def test_terminal_only_tools_are_listed_as_cli_and_gui_apps_are_not(self):
        by_id = {e["id"]: e for e in self.catalog}
        # These print usage and exit (or have no window), so they need the terminal.
        for tool in ("git", "win-bun", "pandoc", "nmap", "starship", "deno", "nodejs"):
            if tool in by_id:
                self.assertTrue(by_id[tool]["cli"], tool)
        # Console-subsystem exes that are really GUI apps must stay ordinary tiles.
        for gui in ("darktable", "scrcpy", "win-ultrastar-deluxe"):
            if gui in by_id:
                self.assertFalse(by_id[gui]["cli"], gui)

    def test_no_orphan_icons_and_none_named_wrongly(self):
        referenced = {e["icon"] for e in self.catalog}
        on_disk = {p.name for p in bc.ICONS_DIR.iterdir() if p.is_file()}
        self.assertEqual(on_disk - referenced, set(), "icon files no entry references")

    def test_no_machine_specific_or_installer_launch_paths(self):
        for e in self.catalog:
            windows = e["bin"].get("windows", "")
            self.assertNotIn("\\users\\", windows.lower(), e["id"])
            self.assertFalse(sw.is_installer_exe(windows) if "\\" in windows else False, e["id"])


if __name__ == "__main__":
    unittest.main()
