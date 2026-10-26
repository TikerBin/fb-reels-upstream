"""独立基线、完整事件不可变、实际推送对象的回归测试（无第三方依赖）。"""

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from changelog_utils import assert_history_unchanged, recompute_envelope
import validate_history as guard


def fixture():
    document = {"events": [{
        "seq": 1, "event_id": "evt-1", "item_id": "item-1", "version": 1,
        "type": "added", "status": "active", "reason": "fixture",
        "occurred_at": "2026-10-17T22:30:00+08:00",
        "details": {"source": "original", "tags": ["a", "b"]},
    }]}
    return recompute_envelope(document, "2026-10-17T22:30:00+08:00")


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture()
        self.candidate = copy.deepcopy(self.base)

    def test_unchanged(self):
        self.assertTrue(assert_history_unchanged(self.base, self.candidate))

    def test_legitimate_append_and_envelope_update(self):
        event = copy.deepcopy(self.base["events"][0])
        event.update(seq=2, event_id="evt-2", version=2, type="modified", reason="时钟错误更正")
        self.candidate["events"].append(event)
        recompute_envelope(self.candidate, "2026-10-18T09:00:00+08:00")
        self.assertTrue(assert_history_unchanged(self.base, self.candidate))
        self.assertEqual(self.base, fixture())

    def test_every_historical_field_is_immutable(self):
        for key, value in {
            "occurred_at": "2026-10-17T21:56:00+08:00", "event_id": "changed",
            "item_id": "changed", "version": 2, "type": "modified",
            "status": "retracted", "reason": "correction",
            "details": {"source": "changed", "tags": ["a", "b"]},
        }.items():
            with self.subTest(field=key):
                candidate = copy.deepcopy(self.base)
                candidate["events"][0][key] = value
                with self.assertRaisesRegex(AssertionError, "历史事件不可改写"):
                    assert_history_unchanged(self.base, candidate)

    def test_added_and_removed_fields(self):
        for remove in (True, False):
            with self.subTest(remove=remove):
                candidate = copy.deepcopy(self.base)
                if remove:
                    del candidate["events"][0]["details"]
                else:
                    candidate["events"][0]["extra"] = None
                with self.assertRaises(AssertionError):
                    assert_history_unchanged(self.base, candidate)

    def test_nested_array_order(self):
        self.candidate["events"][0]["details"]["tags"].reverse()
        with self.assertRaises(AssertionError):
            assert_history_unchanged(self.base, self.candidate)

    def test_boolean_does_not_equal_integer(self):
        self.candidate["events"][0]["version"] = True
        with self.assertRaises(AssertionError):
            assert_history_unchanged(self.base, self.candidate)

    def test_boolean_seq_rejected(self):
        self.candidate["events"][0]["seq"] = True
        with self.assertRaises(AssertionError):
            assert_history_unchanged(self.base, self.candidate)

    def test_deletion_even_after_envelope_recomputed(self):
        self.candidate["events"] = []
        recompute_envelope(self.candidate, "2026-10-18T09:00:00+08:00")
        with self.assertRaisesRegex(AssertionError, "历史事件被删除"):
            assert_history_unchanged(self.base, self.candidate)

    def test_missing_baseline_events_rejected(self):
        for base in ({}, {"events": None}, {"events": {}}):
            with self.subTest(base=base), self.assertRaises(AssertionError):
                assert_history_unchanged(base, self.candidate)

    def test_reordering_and_gap_rejected(self):
        second = copy.deepcopy(self.base["events"][0])
        second.update(seq=2, event_id="evt-2")
        self.base["events"].append(second)
        recompute_envelope(self.base, "2026-10-18T09:00:00+08:00")
        candidate = copy.deepcopy(self.base)
        candidate["events"].reverse()
        with self.assertRaises(AssertionError):
            assert_history_unchanged(self.base, candidate)
        candidate = copy.deepcopy(self.base)
        candidate["events"][1]["seq"] = 3
        recompute_envelope(candidate, "2026-10-18T09:00:00+08:00")
        with self.assertRaises(AssertionError):
            assert_history_unchanged(self.base, candidate)

    def test_duplicate_id_rejected_on_append(self):
        self.candidate["events"].append(copy.deepcopy(self.base["events"][0]))
        self.candidate["events"][1]["seq"] = 2
        recompute_envelope(self.candidate, "2026-10-18T09:00:00+08:00")
        with self.assertRaises(AssertionError):
            assert_history_unchanged(self.base, self.candidate)

    def test_object_key_order_ignored(self):
        self.candidate["events"][0] = dict(reversed(list(self.base["events"][0].items())))
        self.assertTrue(assert_history_unchanged(self.base, self.candidate))

    def test_stale_envelope_still_rejected(self):
        self.candidate["event_count"] = 0
        with self.assertRaises(AssertionError):
            assert_history_unchanged(self.base, self.candidate)


class GateTests(unittest.TestCase):
    def test_cli_leaves_no_python_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("validate_history.py", "changelog_utils.py"):
                (root / name).write_bytes((guard.ROOT / name).read_bytes())
            env = dict(os.environ)
            env.pop("PYTHONDONTWRITEBYTECODE", None)
            result = subprocess.run(
                [sys.executable, str(root / "validate_history.py"), "--help"],
                cwd=root, env=env, capture_output=True
            )
            self.assertEqual(result.returncode, 0)
            self.assertFalse((root / "__pycache__").exists())

    def test_ambiguous_json_rejected(self):
        for source in ('{"events":[],"events":[]}', '{"x":NaN}', '{"x":Infinity}'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                guard.parse(source)

    def test_remote_missing_or_unavailable_fails_closed(self):
        with patch.object(guard, "git", side_effect=ValueError("missing baseline")):
            with self.assertRaises(ValueError):
                guard.validate("missing")

    def test_pre_push_checks_actual_commits(self):
        local, remote = "a" * 40, "b" * 40
        with patch.object(guard, "validate") as validate:
            guard.pre_push([f"refs/heads/main {local} refs/heads/main {remote}\n"])
            validate.assert_called_once_with(remote, local)

    def test_delete_or_recreate_main_blocked(self):
        for local, remote in ((guard.ZERO, "a" * 40), ("a" * 40, guard.ZERO)):
            with self.subTest(local=local), self.assertRaises(ValueError):
                guard.pre_push([f"refs/heads/main {local} refs/heads/main {remote}"])

    def test_invalid_hook_input(self):
        for source in ("invalid", "main not-a-sha refs/heads/main not-a-sha"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                guard.pre_push([source])

    def test_working_candidate_compared_with_separate_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = fixture()
            candidate["events"][0]["occurred_at"] = "2026-10-17T21:56:00+08:00"
            (root / "changelog.json").write_text(json.dumps(candidate), encoding="utf-8")
            with patch.object(guard, "ROOT", root), patch.object(guard, "commit", return_value="a" * 40), patch.object(guard, "git", return_value=json.dumps(fixture())):
                with self.assertRaisesRegex(AssertionError, "occurred_at"):
                    guard.validate("origin/main")

    def test_non_fast_forward_rejected(self):
        with patch.object(guard, "commit", side_effect=["a" * 40, "b" * 40]), patch.object(guard, "git", return_value=json.dumps(fixture())), patch.object(guard.subprocess, "run") as run:
            run.return_value.returncode = 1
            with self.assertRaisesRegex(ValueError, "继承已发布基线"):
                guard.validate("base", "candidate")

    def test_cli_requires_independent_base(self):
        with patch("sys.argv", ["validate_history.py"]), patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                guard.main()
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
