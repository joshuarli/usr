"""End-to-end link parity and adversarial filesystem safety fixtures.

All operations run in freshly-created scratch homes and Git repositories.
The cases mirror the 32 historical sym shell scenarios without installing
anything in the developer's HOME.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from links import LinkError, discover
from link_plan import plan_links
from link_apply import LinkApplyError, Ownership, apply
from ownership import records, read_manifest


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="usr-links-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / "dotfiles/base").mkdir(parents=True)
        (self.root / "dotfiles/linux").mkdir(parents=True)
        self.home = self.root / "home"
        self.home.mkdir()
        self.owned = self.root / "owned"
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def source(self, rel: str, text: str = "content", layer: str = "base") -> Path:
        path = self.root / "dotfiles" / layer / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def marker(self, rel: str, layer: str = "base") -> None:
        self.source(rel + "/.sym-dir", "", layer)

    def track(self) -> None:
        subprocess.run(["git", "-C", str(self.root), "add", "dotfiles/base", "dotfiles/linux"], check=True)

    def plan(self, target: Path | None = None):
        target = target or self.home
        return plan_links(discover(self.root, target, "linux"), self.owned)

    def sync(self):
        plan = self.plan()
        self.assertFalse(plan.conflicts, plan.conflicts)
        apply(plan, self.owned)
        return plan

    def test_01_clean_plan_and_no_mutation(self):
        self.source(".bashrc")
        p = self.plan()
        self.assertEqual([a.kind for a in p.actions], ["link"])
        self.assertFalse((self.home / ".bashrc").exists())
        self.assertTrue(p.lines()[0].startswith("LINK: "))
        self.assertFalse(self.owned.exists())

    def test_02_foreign_file_conflicts_even_in_plan(self):
        self.source(".bashrc")
        (self.home / ".bashrc").write_text("foreign")
        p = self.plan()
        self.assertTrue(p.conflicts)
        with self.assertRaises(LinkApplyError): apply(p, self.owned)
        self.assertEqual((self.home / ".bashrc").read_text(), "foreign")

    def test_03_target_must_exist(self):
        with self.assertRaises(LinkError): self.plan(self.home / "missing")

    def test_04_nested_creates_relative_links(self):
        src = self.source(".config/mpv/mpv.conf", "x")
        self.source(".bashrc", "a")
        self.track()
        self.sync()
        self.assertTrue((self.home / ".config/mpv/mpv.conf").is_symlink())
        self.assertEqual((self.home / ".config/mpv/mpv.conf").resolve(), src)
        self.assertEqual(os.readlink(self.home / ".bashrc"), os.path.relpath(self.root / "dotfiles/base/.bashrc", self.home))

    def test_05_no_partial_apply_when_one_conflict(self):
        self.source("a")
        self.source("b")
        (self.home / "b").write_text("foreign")
        p = self.plan()
        with self.assertRaises(LinkApplyError): apply(p, self.owned)
        self.assertFalse((self.home / "a").exists())

    def test_06_repeat_is_idempotent(self):
        self.source(".config/mpv/mpv.conf")
        self.sync()
        self.assertTrue(self.plan().converged)
        self.sync()
        self.assertEqual(sum(k == "F" for k, _ in records(self.owned)), 1)

    def test_07_alternate_absolute_link_resolving_same_source(self):
        src = self.source(".bashrc")
        (self.home / ".bashrc").symlink_to(src)
        self.assertTrue(self.plan().converged)
        self.assertFalse(self.owned.exists())

    def test_08_nested_link_and_file_records(self):
        self.source(".config/mpv/mpv.conf")
        self.sync()
        r = records(self.owned)
        self.assertIn(("F", self.home / ".config/mpv/mpv.conf"), r)
        self.assertIn(("E", self.home / ".config/mpv"), r)
        self.assertIn(("E", self.home / ".config"), r)
        self.assertEqual(len(read_manifest(self.owned)), 1)

    def test_09_unmanaged_symlink_is_conflict(self):
        self.source(".bashrc")
        (self.home / ".bashrc").symlink_to(self.root / "alien")
        self.assertTrue(self.plan().conflicts)

    def test_10_existing_non_symlink_is_conflict(self):
        self.source(".config/mpv/mpv.conf")
        (self.home / ".config/mpv").mkdir(parents=True)
        (self.home / ".config/mpv/mpv.conf").write_text("foreign")
        self.assertTrue(self.plan().conflicts)

    def test_11_whole_directory_and_ignore(self):
        self.marker("agent")
        self.source("agent/keep.txt")
        self.source("agent/generated.log")
        self.source("agent/.gitignore", "generated.log\n")
        self.track()
        self.sync()
        self.assertTrue((self.home / "agent").is_symlink())
        self.assertEqual(len([p for p in self.home.iterdir() if p.is_symlink()]), 1)
        self.assertTrue(self.plan().converged)

    def test_12_source_link_with_matching_text_into_target(self):
        dest = self.home / ".a/link"
        dest.parent.mkdir()
        (self.home / ".b/real").mkdir(parents=True)
        (self.home / ".b/real/g").write_text("g")
        path = self.root / "dotfiles/base/.a/link"
        path.parent.mkdir()
        path.symlink_to("../.b/real")
        self.source(".b/real/f")
        dest.symlink_to("../.b/real")
        self.sync()
        self.assertEqual(os.readlink(dest), "../.b/real")
        self.assertTrue((self.home / ".b/real/f").is_symlink())
        dest.unlink(); dest.symlink_to("../elsewhere")
        self.assertTrue(self.plan().conflicts)

    def test_13_unresolved_existing_dangling_link_conflicts(self):
        path = self.root / "dotfiles/base/.a/link"
        path.parent.mkdir(); path.symlink_to("../x/y")
        (self.home / ".a").mkdir()
        (self.home / ".a/link").symlink_to("../x/y")
        self.assertTrue(self.plan().conflicts)

    def test_14_symlinked_parent_outside_home_refused(self):
        self.source(".tool/agent/settings.json")
        (self.home / ".tool").mkdir()
        (self.home / ".tool/agent").symlink_to(self.root / "dotfiles/base/.tool/agent")
        p = self.plan()
        self.assertTrue(any("unsafe symlinked parent" in x for x in p.conflicts))
        with self.assertRaises(LinkApplyError): apply(p, self.owned)

    def test_15_outside_ancestors_preserved(self):
        self.source(".a/f")
        target = self.root / "outer/keep/home"
        target.mkdir(parents=True)
        p = self.plan(target)
        apply(p, self.owned)
        self.assertTrue((target / ".a/f").is_symlink())
        self.assertTrue(target.is_dir())

    def test_16_gitignored_and_non_ascii(self):
        self.source(".cfg/keep")
        self.source(".cfg/skip.log")
        self.source(".cfg/café")
        self.source(".gitignore", "skip.log\n")
        self.sync()
        self.assertTrue((self.home / ".cfg/keep").is_symlink())
        self.assertTrue((self.home / ".cfg/café").is_symlink())
        self.assertFalse((self.home / ".cfg/skip.log").exists())

    def test_17_non_git_discovery(self):
        # A source outside every Git worktree must use filesystem discovery.
        with tempfile.TemporaryDirectory(prefix="non-git-links-") as external:
            root = Path(external)
            layer = root / "dotfiles/base"
            (layer / ".a").mkdir(parents=True)
            (layer / ".a/f").write_text("f")
            (layer / "d").mkdir()
            (layer / "d/.sym-dir").touch()
            (layer / "d/g").write_text("g")
            d = discover(root, self.home, "linux")
            p = plan_links(d, self.owned)
            self.assertEqual(len(p.actions), 2)
            apply(p, self.owned)
            self.assertTrue((self.home / ".a/f").is_symlink())
            self.assertTrue((self.home / "d").is_symlink())

    def test_18_nested_markers_only_outer_link(self):
        self.marker(".a")
        self.marker(".a/inner")
        self.source(".a/inner/f")
        p = self.plan()
        self.assertEqual([a.path for a in p.actions], [self.home / ".a"])

    def test_19_foreign_directory_link_conflicts(self):
        self.marker(".a")
        (self.home / ".a").symlink_to(self.root / "alien")
        self.assertTrue(self.plan().conflicts)

    def test_20_symlinked_target_root_supported(self):
        self.source(".f/g")
        actual = self.root / "real/tg"
        actual.mkdir(parents=True)
        (self.root / "target-link").symlink_to(actual)
        plan = self.plan(self.root / "target-link")
        apply(plan, self.owned)
        self.assertTrue((actual / ".f/g").is_symlink())

    def test_21_dangling_source_link_becomes_valid_after_directory_link(self):
        self.marker(".agents/skills")
        self.source(".agents/skills/keep")
        dest = self.root / "dotfiles/base/.claude/skills"
        dest.parent.mkdir(); dest.symlink_to("../.agents/skills")
        (self.home / ".claude").mkdir()
        (self.home / ".claude/skills").symlink_to("../.agents/skills")
        p = self.plan()
        self.assertFalse(p.conflicts, p.conflicts)
        apply(p, self.owned)
        self.assertTrue((self.home / ".claude/skills/keep").exists())

    def test_22_no_path_traversal_through_discovery(self):
        self.source("a")
        p = self.plan()
        self.assertTrue(all(a.path.is_relative_to(self.home) for a in p.actions))
        self.assertEqual(len(p.actions), 1)

    def test_23_ownership_only_claims_created_entries(self):
        self.source(".cfg/f")
        self.sync()
        before = self.owned.read_text()
        self.sync()
        self.assertEqual(self.owned.read_text(), before)

    def test_24_preexisting_correct_link_unclaimed(self):
        src = self.source(".cfg/f")
        (self.home / ".cfg").mkdir()
        (self.home / ".cfg/f").symlink_to(src)
        self.sync()
        self.assertFalse(self.owned.exists())

    def test_25_root_level_parent_confined(self):
        from link_plan import _inside
        self.assertTrue(_inside(Path("/etc"), Path("/")))

    def test_26_root_target_can_plan_existing_subdir(self):
        from link_plan import _parent_safe
        from links import Discovery
        d = Discovery(Path("/"), (self.root / "source",), ())
        self.assertTrue(_parent_safe(Path("/etc/passwd"), d))

    def test_27_prune_removed_source_but_keep_unowned(self):
        self.source(".keep")
        self.source(".stale")
        self.sync()
        (self.home / ".unowned").symlink_to(self.root / "elsewhere")
        (self.root / "dotfiles/base/.stale").unlink()
        p = self.plan()
        self.assertEqual([a.kind for a in p.actions], ["prune"])
        apply(p, self.owned)
        self.assertFalse((self.home / ".stale").is_symlink())
        self.assertTrue((self.home / ".keep").is_symlink())
        self.assertTrue((self.home / ".unowned").is_symlink())
        self.assertNotIn(("F", self.home / ".stale"), records(self.owned))

    def test_48_prune_removed_layer_symlink_mirrored_into_target(self):
        self.source(".codex/AGENTS.md")
        adapter = self.root / "dotfiles/base/.claude/AGENTS.md"
        adapter.parent.mkdir()
        adapter.symlink_to("../.codex/AGENTS.md")
        self.track()
        self.sync()
        dest = self.home / ".claude/AGENTS.md"
        self.assertEqual(os.readlink(dest), "../.codex/AGENTS.md")
        adapter.unlink()
        p = self.plan()
        self.assertEqual([(a.kind, a.path) for a in p.actions], [("prune", dest)])
        apply(p, self.owned)
        self.assertFalse(dest.is_symlink())
        self.assertTrue((self.home / ".codex/AGENTS.md").is_symlink())

    def test_49_mirrored_link_kept_when_target_no_longer_provided(self):
        adapter = self.root / "dotfiles/base/.claude/AGENTS.md"
        adapter.parent.mkdir(parents=True)
        adapter.symlink_to("../.codex/AGENTS.md")
        self.track()
        self.sync()
        dest = self.home / ".claude/AGENTS.md"
        adapter.unlink()
        self.assertNotIn(dest, [a.path for a in self.plan().actions])

    def test_28_tab_name_rejected_before_changes(self):
        self.source("a\tb")
        with self.assertRaises(LinkError): self.plan()
        self.assertFalse((self.home / "a\tb").exists())

    def test_29_backslash_in_tmp_directory_does_not_matter(self):
        self.marker(".cfg")
        self.source(".cfg/f")
        apply(self.plan(), self.owned)
        self.assertTrue((self.home / ".cfg").is_symlink())

    def test_30_tab_target_is_rejected(self):
        target = self.root / "with\ttab"
        target.mkdir()
        self.source(".a")
        with self.assertRaises(LinkError): self.plan(target)

    def test_31_move_between_layers_is_one_reconcile(self):
        src = self.source(".moved")
        self.sync()
        new = self.root / "dotfiles/linux/.moved"
        src.rename(new)
        p = self.plan()
        self.assertEqual([a.kind for a in p.actions], ["replace"])
        apply(p, self.owned)
        self.assertEqual((self.home / ".moved").resolve(), new)
        self.assertTrue(self.plan().converged)

    def test_32_absent_records_are_forgotten(self):
        src = self.source(".stale")
        self.sync()
        src.unlink()
        (self.home / ".stale").unlink()
        p = self.plan()
        self.assertEqual([a.kind for a in p.actions], ["forget"])
        apply(p, self.owned)
        self.assertNotIn(("F", self.home / ".stale"), records(self.owned))

    def test_33_injected_foreign_file_at_apply_is_preserved(self):
        self.source(".a")
        p = self.plan()
        (self.home / ".a").write_text("foreign")
        with self.assertRaisesRegex(LinkApplyError, "changed since planning"):
            apply(p, self.owned)
        self.assertEqual((self.home / ".a").read_text(), "foreign")

    def test_34_previously_owned_path_replaced_with_file_is_preserved(self):
        self.source(".a")
        self.sync()
        (self.home / ".a").unlink()
        (self.home / ".a").write_text("custom")
        self.source(".b")
        p = self.plan()
        self.assertTrue(p.conflicts)
        with self.assertRaises(LinkApplyError): apply(p, self.owned)
        self.assertEqual((self.home / ".a").read_text(), "custom")
        self.assertFalse((self.home / ".b").exists())

    def test_35_overlapping_layer_link_claims_rejected(self):
        self.source(".dup", layer="base")
        self.source(".dup", layer="linux")
        with self.assertRaisesRegex(LinkError, "duplicate"):
            self.plan()

    def test_36_existing_parent_escape_blocked(self):
        self.source(".dir/f")
        (self.home / ".dir").symlink_to(self.root / "outside")
        (self.root / "outside").mkdir()
        self.assertTrue(self.plan().conflicts)
        self.assertFalse((self.root / "outside/f").exists())

    def test_37_unknown_legacy_owned_link_not_deleted_while_source_exists(self):
        src = self.source(".a")
        (self.home / ".a").symlink_to(src)
        self.owned.write_text(f"F\t{self.home / '.a'}\n")
        self.sync()
        self.assertTrue((self.home / ".a").is_symlink())
        self.assertNotIn(str(self.home / ".a"), read_manifest(self.owned))

    def test_39_prune_never_removes_a_replaced_foreign_symlink(self):
        src = self.source(".gone")
        self.sync()
        src.unlink()
        destination = self.home / ".gone"
        destination.unlink()
        outside = self.root / "unmanaged"
        outside.write_text("keep")
        destination.symlink_to(outside)
        p = self.plan()
        self.assertTrue(destination.is_symlink())
        self.assertNotIn(destination, [a.path for a in p.actions])
        self.assertEqual(destination.resolve(), outside)

    def test_42_same_source_replacement_never_pruned_as_owned(self):
        src = self.source(".gone")
        self.sync()
        dest = self.home / ".gone"
        original = os.readlink(dest)
        dest.unlink()
        dest.symlink_to(src)
        self.assertNotEqual(os.readlink(dest), original)
        self.assertTrue(self.plan().converged)
        src.unlink()
        plan = self.plan()
        self.assertNotIn(dest, [a.path for a in plan.actions])
        apply(plan, self.owned)
        self.assertTrue(dest.is_symlink())
        self.assertEqual(os.readlink(dest), str(src))

    def test_43_legacy_record_cannot_authorize_prune(self):
        src = self.source(".old")
        dest = self.home / ".old"
        dest.symlink_to(src)
        self.owned.write_text(f"F\t{dest}\n")
        src.unlink()
        self.assertNotIn(dest, [a.path for a in self.plan().actions])
        self.assertTrue(dest.is_symlink())

    def test_44_persistence_failure_after_symlink_is_recovered(self):
        self.source(".tracked")
        initial = self.plan()
        with patch.object(Ownership, "_save_records", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                apply(initial, self.owned)
        destination = self.home / ".tracked"
        self.assertTrue(destination.is_symlink())
        pending = self.plan()
        self.assertEqual(list(pending.pending), [destination])
        self.assertFalse(pending.converged)
        self.assertEqual([a.kind for a in pending.actions], [])
        apply(pending, self.owned)
        self.assertTrue(self.plan().converged)
        self.assertIn(str(destination), read_manifest(self.owned))
        self.assertFalse(list(Path(str(self.owned) + ".pending-links").glob("*.json")))

    def test_45_manifest_failure_after_record_is_recovered(self):
        self.source(".tracked")
        with patch.object(Ownership, "_save_proofs", side_effect=OSError("write failed")):
            with self.assertRaisesRegex(OSError, "write failed"):
                apply(self.plan(), self.owned)
        self.assertIn(("F", self.home / ".tracked"), records(self.owned))
        self.assertNotIn(str(self.home / ".tracked"), read_manifest(self.owned))
        apply(self.plan(), self.owned)
        self.assertTrue(self.plan().converged)
        self.assertIn(str(self.home / ".tracked"), read_manifest(self.owned))

    def test_46_recovery_never_adopts_foreign_replacement(self):
        self.source(".tracked")
        with patch.object(Ownership, "_save_records", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                apply(self.plan(), self.owned)
        dest = self.home / ".tracked"
        dest.unlink()
        dest.symlink_to(self.root / "foreign")
        with self.assertRaisesRegex(LinkApplyError, "pending link destination changed"):
            apply(self.plan(), self.owned)
        self.assertEqual(dest.resolve(), self.root / "foreign")

    def test_47_retry_create_with_existing_stage_relinks_original_inode(self):
        self.source(".tracked")
        import link_apply
        raw_link = link_apply.os.link
        count = 0
        def fail_once(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 1:
                raise OSError("crash before install")
            return raw_link(*args, **kwargs)
        with patch.object(link_apply.os, "link", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "crash before install"):
                apply(self.plan(), self.owned)
        self.assertFalse((self.home / ".tracked").exists())
        self.assertFalse(self.plan().converged)
        apply(self.plan(), self.owned)
        self.assertTrue(self.plan().converged)
        self.assertTrue((self.home / ".tracked").is_symlink())

    def test_40_internal_parent_symlink_stays_confined(self):
        self.source(".a/f")
        internal = self.home / "inside"
        internal.mkdir()
        (self.home / ".a").symlink_to(internal)
        p = self.plan()
        self.assertFalse(p.conflicts)
        apply(p, self.owned)
        self.assertTrue((internal / "f").is_symlink())

    def test_41_reject_changed_parent_between_plan_and_apply(self):
        self.source(".dir/f")
        (self.home / ".dir").mkdir()
        p = self.plan()
        (self.home / ".dir").rmdir()
        outside = self.root / "out"
        outside.mkdir()
        (self.home / ".dir").symlink_to(outside)
        with self.assertRaises(LinkApplyError):
            apply(p, self.owned)
        self.assertFalse((outside / "f").exists())

    def test_38_validate_mode_does_not_rewrite_ownership(self):
        self.source(".a")
        self.sync()
        prior = self.owned.read_bytes()
        prior_proof = (Path(str(self.owned) + ".verified.json")).read_bytes()
        self.assertTrue(self.plan().converged)
        self.assertEqual(self.owned.read_bytes(), prior)
        self.assertEqual(Path(str(self.owned) + ".verified.json").read_bytes(), prior_proof)


if __name__ == "__main__":
    unittest.main()
