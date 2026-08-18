#!/usr/bin/env python3
"""Exercise graph, ownership, evidence, transition, and recovery behavior."""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

import workflow

SCRIPT_DIR = Path(__file__).resolve().parent
FIXTURES = SCRIPT_DIR / "fixtures"
WORKFLOW = SCRIPT_DIR / "workflow.py"


def fixture(name: str) -> Dict[str, Any]:
    return workflow.read_state(FIXTURES / name)


def run_cli(
    *arguments: str,
    expected: int = 0,
    directory: Optional[Path] = None,
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(WORKFLOW)] + list(arguments),
        cwd=str(directory or SCRIPT_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != expected:
        raise AssertionError(
            "expected exit {}, got {}\nstdout:\n{}\nstderr:\n{}".format(
                expected, result.returncode, result.stdout, result.stderr
            )
        )
    return result


class WorkflowTests(unittest.TestCase):
    def test_ready_ticket_is_selected_after_done_blocker(self) -> None:
        action = workflow.next_action(fixture("ready-blocked-done.json"))
        self.assertEqual(
            action, {"action": "spawn_ticket_coordinator", "ticket": "002"}
        )

    def test_graph_rejects_missing_blocker(self) -> None:
        state = fixture("ready-blocked-done.json")
        state["tickets"][1]["blockers"] = ["999"]
        self.assertIn(
            "ticket 002 references missing blocker 999", workflow.graph_errors(state)
        )

    def test_graph_rejects_cycle(self) -> None:
        state = fixture("ready-blocked-done.json")
        state["tickets"][0]["phase"] = "queued"
        state["tickets"][0]["blockers"] = ["002"]
        errors = workflow.graph_errors(state)
        self.assertTrue(
            any(error.startswith("ticket graph cycle:") for error in errors)
        )

    def test_closed_ticket_without_evidence_is_invalid(self) -> None:
        state = fixture("invalid-transition.json")
        state["evidence"] = {}
        errors = workflow.state_errors(state)
        self.assertIn("closed ticket 001: ticket 001 has no evidence object", errors)

    def test_event_sequence_must_match_last_event(self) -> None:
        state = fixture("interrupted-recovery.json")
        state["eventSequence"] = 3
        self.assertIn(
            "lastEvent.sequence must equal eventSequence", workflow.graph_errors(state)
        )

    def test_invalid_transition_is_rejected_without_mutation(self) -> None:
        state = fixture("invalid-transition.json")
        original = copy.deepcopy(state)
        with self.assertRaises(workflow.WorkflowError) as context:
            workflow.transition(state, "001", "coordinating", "/root", "", None)
        self.assertEqual(context.exception.exit_code, 3)
        self.assertEqual(state, original)

    def test_non_frontier_ticket_cannot_start(self) -> None:
        state = fixture("ready-blocked-done.json")
        state["tickets"][2]["phase"] = "queued"
        state["tickets"][2].pop("blockerReason")
        with self.assertRaises(workflow.WorkflowError) as context:
            workflow.transition(
                state, "003", "coordinating", "/root", "", "3-in-progress"
            )
        self.assertIn(
            "not the next dependency-ready frontier ticket", str(context.exception)
        )

    def test_gap_transition_records_routable_reason(self) -> None:
        state = fixture("successful-completion.json")
        state["tickets"][0]["phase"] = "acceptance"
        event = workflow.transition(
            state, "001", "gap", "/root", "AC1 lacks runtime proof", None
        )
        self.assertEqual(event["to"], "gap")
        action = workflow.next_action(state)
        self.assertEqual(action["action"], "return_acceptance_gaps")
        self.assertIn("AC1 lacks runtime proof", action["gaps"])

    def test_overlapping_live_ownership_is_rejected(self) -> None:
        errors = workflow.assignment_errors(fixture("overlapping-ownership.json"))
        self.assertTrue(any("ownership overlap" in error for error in errors))

    def test_done_assignment_does_not_conflict_with_live_ownership(self) -> None:
        state = fixture("overlapping-ownership.json")
        state["assignments"][0]["status"] = "done"
        self.assertFalse(
            any(
                "ownership overlap" in error
                for error in workflow.assignment_errors(state)
            )
        )

    def test_missing_evidence_rejects_truthful_closure(self) -> None:
        gaps = workflow.closure_gaps(fixture("missing-evidence.json"), "001")
        expected_fragments = (
            "lacks a named observation",
            "no executed tests",
            "snapshot inspected is not proven",
            "runtime evidence is incomplete",
            "Apple verification lane remains leased",
            "contains unrelated work",
            "material omissions",
            "lacks authority",
            "unauthorized actions",
        )
        for fragment in expected_fragments:
            self.assertTrue(any(fragment in gap for gap in gaps), fragment)

    def test_not_applicable_evidence_must_be_explicit(self) -> None:
        state = fixture("successful-completion.json")
        del state["evidence"]["001"]["snapshots"]["required"]
        self.assertIn(
            "snapshots.required must be explicit",
            workflow.closure_gaps(state, "001"),
        )

    def test_interrupted_ticket_derives_recovery_action(self) -> None:
        action = workflow.next_action(fixture("interrupted-recovery.json"))
        self.assertEqual(action["action"], "respawn_ticket_coordinator")
        self.assertEqual(action["ticket"], "001")
        self.assertEqual(
            action["recoveredState"]["completedAssignments"], ["/root/ticket_001/scout"]
        )
        self.assertEqual(
            action["recoveredState"]["unresolvedAssignments"], ["/root/ticket_001"]
        )

    def test_fresh_coordinator_can_acknowledge_recovery(self) -> None:
        state = fixture("interrupted-recovery.json")
        state["assignments"][0]["agent"] = "/root/ticket_001_recovery"
        event = workflow.mark_resumed(state, "001", "/root/ticket_001_recovery")
        self.assertEqual(event["type"], "recovered")
        self.assertFalse(state["tickets"][0]["interrupted"])
        self.assertEqual(
            workflow.next_action(state),
            {"action": "wait_ticket_coordinator", "ticket": "001"},
        )

    def test_recovery_rejects_an_actor_without_the_live_assignment(self) -> None:
        state = fixture("interrupted-recovery.json")
        original = copy.deepcopy(state)
        with self.assertRaises(workflow.WorkflowError) as context:
            workflow.mark_resumed(state, "001", "/root/other")
        self.assertEqual(context.exception.exit_code, 3)
        self.assertEqual(state, original)

    def test_complete_evidence_allows_close_transition(self) -> None:
        state = fixture("successful-completion.json")
        event = workflow.transition(
            state, "001", "closed", "/root", "acceptance passed", "4-done"
        )
        self.assertEqual(event["from"], "ready_to_close")
        self.assertEqual(state["tickets"][0]["phase"], "closed")
        self.assertEqual(workflow.next_action(state), {"action": "run_complete"})

    def test_cli_rejection_preserves_state_and_writes_no_event(self) -> None:
        with tempfile.TemporaryDirectory(prefix="multi-ticket-reject-") as temporary:
            root = Path(temporary)
            state_path = root / "run.json"
            shutil.copyfile(str(FIXTURES / "missing-evidence.json"), str(state_path))
            before = state_path.read_text(encoding="utf-8")
            result = run_cli(
                "transition",
                "--state",
                str(state_path),
                "--ticket",
                "001",
                "--to",
                "closed",
                "--actor",
                "/root",
                expected=3,
            )
            self.assertIn("closure rejected", json.loads(result.stdout)["error"])
            self.assertEqual(state_path.read_text(encoding="utf-8"), before)
            self.assertFalse((root / "events.jsonl").exists())

    def test_cli_close_is_atomic_and_emits_compact_event(self) -> None:
        with tempfile.TemporaryDirectory(prefix="multi-ticket-close-") as temporary:
            root = Path(temporary)
            state_path = root / "run.json"
            shutil.copyfile(
                str(FIXTURES / "successful-completion.json"), str(state_path)
            )
            result = run_cli(
                "transition",
                "--state",
                str(state_path),
                "--ticket",
                "001",
                "--to",
                "closed",
                "--actor",
                "/root",
                "--reason",
                "acceptance passed",
                "--repository-status",
                "4-done",
            )
            payload = json.loads(result.stdout)
            self.assertTrue(payload["changed"])
            self.assertEqual(payload["next"], {"action": "run_complete"})
            self.assertNotIn("\n", result.stdout.strip())
            events = (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(events), 1)
            self.assertEqual(json.loads(events[0])["sequence"], 1)
            self.assertEqual(workflow.read_state(state_path)["eventSequence"], 1)


def dry_run() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="multi-ticket-dry-run-") as temporary:
        root = Path(temporary)

        recovery_path = root / "recovery.json"
        shutil.copyfile(str(FIXTURES / "interrupted-recovery.json"), str(recovery_path))
        recovery = json.loads(run_cli("next", "--state", str(recovery_path)).stdout)
        recovery_state = workflow.read_state(recovery_path)
        recovery_state["assignments"][0]["agent"] = "/root/ticket_001_recovery"
        workflow.write_state(recovery_path, recovery_state)
        resumed = json.loads(
            run_cli(
                "resume",
                "--state",
                str(recovery_path),
                "--ticket",
                "001",
                "--actor",
                "/root/ticket_001_recovery",
            ).stdout
        )

        rejection_path = root / "rejection.json"
        shutil.copyfile(str(FIXTURES / "missing-evidence.json"), str(rejection_path))
        rejection = json.loads(
            run_cli(
                "transition",
                "--state",
                str(rejection_path),
                "--ticket",
                "001",
                "--to",
                "closed",
                "--actor",
                "/root",
                expected=3,
            ).stdout
        )

        completion_dir = root / "completion"
        completion_dir.mkdir()
        completion_path = completion_dir / "run.json"
        shutil.copyfile(
            str(FIXTURES / "successful-completion.json"), str(completion_path)
        )
        accepted = json.loads(
            run_cli(
                "transition",
                "--state",
                str(completion_path),
                "--ticket",
                "001",
                "--to",
                "closed",
                "--actor",
                "/root",
                "--reason",
                "dry-run acceptance passed",
                "--repository-status",
                "4-done",
            ).stdout
        )
        complete = json.loads(run_cli("next", "--state", str(completion_path)).stdout)
        event_count = len(
            (completion_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        )

        return {
            "recoveryAction": recovery["action"],
            "recoveredTicket": recovery["ticket"],
            "recoveredUnresolvedAssignments": recovery["recoveredState"][
                "unresolvedAssignments"
            ],
            "recoveryResumeAction": resumed["next"]["action"],
            "closureRejection": rejection["error"].split(":", 1)[0],
            "acceptedTransition": accepted["event"]["to"],
            "finalAction": complete["action"],
            "eventCount": event_count,
        }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps(dry_run(), sort_keys=True, separators=(",", ":")))
        return 0
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WorkflowTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
