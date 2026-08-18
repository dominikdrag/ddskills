#!/usr/bin/env python3
"""Validate and advance deterministic state for a coordinated ticket run."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_VERSION = 1
PHASES = {
    "queued",
    "coordinating",
    "acceptance",
    "gap",
    "ready_to_close",
    "blocked",
    "closed",
}
ACTIVE_PHASES = {"coordinating", "acceptance", "gap", "ready_to_close"}
ASSIGNMENT_STATUSES = {"pending", "active", "done", "blocked"}
LIVE_ASSIGNMENT_STATUSES = {"pending", "active", "blocked"}
ROLES = {
    "ticket-coordinator",
    "scout",
    "worker",
    "complex-worker",
    "reviewer",
    "qa-worker",
    "acceptance-checker",
}
ALLOWED_TRANSITIONS = {
    "queued": {"coordinating", "blocked"},
    "coordinating": {"acceptance", "blocked"},
    "acceptance": {"gap", "ready_to_close", "blocked"},
    "gap": {"coordinating", "acceptance", "blocked"},
    "ready_to_close": {"closed"},
    "blocked": {"queued", "coordinating"},
    "closed": set(),
}


class WorkflowError(Exception):
    """A deterministic state or transition error."""

    def __init__(self, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def read_state(path: Path) -> Dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowError("cannot read state {}: {}".format(path, error))
    if not isinstance(payload, dict):
        raise WorkflowError("state root must be a JSON object")
    return payload


def write_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("{}.{}.tmp".format(path.name, os.getpid()))
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def tickets_by_id(state: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    tickets = state.get("tickets", [])
    if not isinstance(tickets, list):
        return {}
    return {
        str(ticket.get("id")): ticket
        for ticket in tickets
        if isinstance(ticket, dict) and ticket.get("id") is not None
    }


def natural_key(value: str) -> Tuple[Any, ...]:
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", value)
    )


def ticket_sort_key(ticket: Dict[str, Any]) -> Tuple[Any, ...]:
    order = ticket.get("order")
    if isinstance(order, int) and not isinstance(order, bool):
        return (0, order, natural_key(str(ticket.get("id", ""))))
    return (1, natural_key(str(ticket.get("id", ""))))


def graph_errors(state: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if state.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("schemaVersion must equal {}".format(SCHEMA_VERSION))
    if not isinstance(state.get("runId"), str) or not state.get("runId", "").strip():
        errors.append("runId must be a non-empty string")
    event_sequence = state.get("eventSequence", 0)
    if (
        not isinstance(event_sequence, int)
        or isinstance(event_sequence, bool)
        or event_sequence < 0
    ):
        errors.append("eventSequence must be a non-negative integer")
    last_event = state.get("lastEvent")
    if event_sequence > 0:
        if not isinstance(last_event, dict):
            errors.append("lastEvent must exist when eventSequence is positive")
        elif last_event.get("sequence") != event_sequence:
            errors.append("lastEvent.sequence must equal eventSequence")
    elif last_event is not None:
        errors.append("lastEvent requires a positive eventSequence")

    tickets = state.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        errors.append("tickets must be a non-empty array")
        return errors

    seen = set()
    valid_tickets: List[Dict[str, Any]] = []
    for index, ticket in enumerate(tickets):
        prefix = "tickets[{}]".format(index)
        if not isinstance(ticket, dict):
            errors.append("{} must be an object".format(prefix))
            continue
        ticket_id = ticket.get("id")
        if not isinstance(ticket_id, str) or not ticket_id.strip():
            errors.append("{}.id must be a non-empty string".format(prefix))
            continue
        if ticket_id in seen:
            errors.append("duplicate ticket id: {}".format(ticket_id))
        seen.add(ticket_id)
        valid_tickets.append(ticket)
        if ticket.get("phase") not in PHASES:
            errors.append(
                "ticket {} has invalid phase: {}".format(ticket_id, ticket.get("phase"))
            )
        if (
            not isinstance(ticket.get("repositoryStatus"), str)
            or not ticket.get("repositoryStatus", "").strip()
        ):
            errors.append("ticket {} must record repositoryStatus".format(ticket_id))
        blockers = ticket.get("blockers", [])
        if not isinstance(blockers, list) or any(
            not isinstance(item, str) for item in blockers
        ):
            errors.append(
                "ticket {} blockers must be an array of ticket ids".format(ticket_id)
            )
        if (
            ticket.get("phase") == "blocked"
            and not str(ticket.get("blockerReason", "")).strip()
        ):
            errors.append(
                "blocked ticket {} must record blockerReason".format(ticket_id)
            )
        if ticket.get("phase") == "gap":
            acceptance_gaps = ticket.get("acceptanceGaps")
            if (
                not isinstance(acceptance_gaps, list)
                or not acceptance_gaps
                or any(
                    not isinstance(item, str) or not item.strip()
                    for item in acceptance_gaps
                )
            ):
                errors.append(
                    "gap ticket {} must record acceptanceGaps".format(ticket_id)
                )

    known = {str(ticket.get("id")) for ticket in valid_tickets}
    for ticket in valid_tickets:
        ticket_id = str(ticket.get("id"))
        blockers = ticket.get("blockers", [])
        if not isinstance(blockers, list):
            continue
        for blocker in blockers:
            if blocker == ticket_id:
                errors.append("ticket {} cannot block itself".format(ticket_id))
            elif blocker not in known:
                errors.append(
                    "ticket {} references missing blocker {}".format(ticket_id, blocker)
                )

    visiting = set()
    visited = set()
    graph = {
        str(ticket.get("id")): list(ticket.get("blockers", []))
        for ticket in valid_tickets
        if isinstance(ticket.get("blockers", []), list)
    }

    def visit(ticket_id: str, path: List[str]) -> None:
        if ticket_id in visiting:
            cycle_start = path.index(ticket_id) if ticket_id in path else 0
            errors.append(
                "ticket graph cycle: {}".format(
                    " -> ".join(path[cycle_start:] + [ticket_id])
                )
            )
            return
        if ticket_id in visited:
            return
        visiting.add(ticket_id)
        for blocker in graph.get(ticket_id, []):
            if blocker in graph:
                visit(blocker, path + [ticket_id])
        visiting.remove(ticket_id)
        visited.add(ticket_id)

    for candidate in sorted(graph, key=natural_key):
        visit(candidate, [])

    active = [
        ticket for ticket in valid_tickets if ticket.get("phase") in ACTIVE_PHASES
    ]
    if len(active) > 1:
        errors.append(
            "only one ticket may own the active coordinator: {}".format(
                ", ".join(str(ticket.get("id")) for ticket in active)
            )
        )
    return unique(errors)


def ownership_overlap(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    if left.get("kind") != right.get("kind"):
        return False
    left_value = str(left.get("value", "")).strip()
    right_value = str(right.get("value", "")).strip()
    if not left_value or not right_value:
        return False
    if left.get("kind") == "seam":
        return left_value == right_value
    if left.get("kind") != "path":
        return False
    left_path = PurePosixPath(left_value)
    right_path = PurePosixPath(right_value)
    return (
        left_path == right_path
        or left_path in right_path.parents
        or right_path in left_path.parents
    )


def assignment_errors(state: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    assignments = state.get("assignments", [])
    if not isinstance(assignments, list):
        return ["assignments must be an array"]
    known_tickets = set(tickets_by_id(state))
    seen_agents = set()
    valid: List[Dict[str, Any]] = []
    for index, assignment in enumerate(assignments):
        prefix = "assignments[{}]".format(index)
        if not isinstance(assignment, dict):
            errors.append("{} must be an object".format(prefix))
            continue
        valid.append(assignment)
        agent = assignment.get("agent")
        if not isinstance(agent, str) or not agent.strip():
            errors.append(
                "{}.agent must be a non-empty canonical target".format(prefix)
            )
        elif agent in seen_agents:
            errors.append("duplicate assignment agent: {}".format(agent))
        else:
            seen_agents.add(agent)
        if assignment.get("role") not in ROLES:
            errors.append(
                "assignment {} has invalid role: {}".format(
                    agent, assignment.get("role")
                )
            )
        if assignment.get("ticket") not in known_tickets:
            errors.append(
                "assignment {} references unknown ticket {}".format(
                    agent, assignment.get("ticket")
                )
            )
        if assignment.get("status") not in ASSIGNMENT_STATUSES:
            errors.append(
                "assignment {} has invalid status: {}".format(
                    agent, assignment.get("status")
                )
            )
        if (
            not isinstance(assignment.get("deliverable"), str)
            or not assignment.get("deliverable", "").strip()
        ):
            errors.append("assignment {} must record a deliverable".format(agent))
        if (
            not isinstance(assignment.get("recipient"), str)
            or not assignment.get("recipient", "").strip()
        ):
            errors.append("assignment {} must record a message recipient".format(agent))
        dependencies = assignment.get("dependsOn", [])
        if not isinstance(dependencies, list) or any(
            not isinstance(item, str) for item in dependencies
        ):
            errors.append(
                "assignment {} dependsOn must be an array of agent targets".format(
                    agent
                )
            )
        ownership = assignment.get("ownership", [])
        if not isinstance(ownership, list):
            errors.append("assignment {} ownership must be an array".format(agent))
            continue
        for item in ownership:
            if (
                not isinstance(item, dict)
                or item.get("kind") not in {"path", "seam"}
                or not str(item.get("value", "")).strip()
            ):
                errors.append("assignment {} has invalid ownership entry".format(agent))
                continue
            if item.get("kind") == "path":
                owned_path = PurePosixPath(str(item.get("value")))
                if (
                    owned_path.is_absolute()
                    or ".." in owned_path.parts
                    or str(owned_path) == "."
                ):
                    errors.append(
                        "assignment {} has unsafe path ownership: {}".format(
                            agent, item.get("value")
                        )
                    )

    known_agents = {
        item.get("agent") for item in valid if isinstance(item.get("agent"), str)
    }
    for assignment in valid:
        agent = assignment.get("agent")
        for dependency in (
            assignment.get("dependsOn", [])
            if isinstance(assignment.get("dependsOn", []), list)
            else []
        ):
            if dependency == agent:
                errors.append("assignment {} cannot depend on itself".format(agent))
            elif dependency not in known_agents:
                errors.append(
                    "assignment {} references missing dependency {}".format(
                        agent, dependency
                    )
                )

    live = [
        assignment
        for assignment in valid
        if assignment.get("status") in LIVE_ASSIGNMENT_STATUSES
    ]
    for index, left in enumerate(live):
        for right in live[index + 1 :]:
            for left_item in (
                left.get("ownership", [])
                if isinstance(left.get("ownership", []), list)
                else []
            ):
                for right_item in (
                    right.get("ownership", [])
                    if isinstance(right.get("ownership", []), list)
                    else []
                ):
                    if (
                        isinstance(left_item, dict)
                        and isinstance(right_item, dict)
                        and ownership_overlap(left_item, right_item)
                    ):
                        errors.append(
                            "ownership overlap between {} and {}: {}".format(
                                left.get("agent"),
                                right.get("agent"),
                                left_item.get("value"),
                            )
                        )
    return unique(errors)


def closure_gaps(
    state: Dict[str, Any], ticket_id: str, include_assignment_errors: bool = True
) -> List[str]:
    gaps: List[str] = []
    ticket = tickets_by_id(state).get(ticket_id)
    if ticket is None:
        return ["unknown ticket: {}".format(ticket_id)]
    evidence_root = state.get("evidence", {})
    evidence = evidence_root.get(ticket_id) if isinstance(evidence_root, dict) else None
    if not isinstance(evidence, dict):
        return ["ticket {} has no evidence object".format(ticket_id)]

    criteria = evidence.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        gaps.append("ticket {} has no acceptance criteria evidence".format(ticket_id))
    else:
        for index, criterion in enumerate(criteria):
            label = (
                str(criterion.get("id", index + 1))
                if isinstance(criterion, dict)
                else str(index + 1)
            )
            if not isinstance(criterion, dict):
                gaps.append("criterion {} is not an object".format(label))
                continue
            if criterion.get("checked") is not True:
                gaps.append("criterion {} is not checked".format(label))
            if not str(criterion.get("observation", "")).strip():
                gaps.append("criterion {} lacks a named observation".format(label))
            if not str(criterion.get("location", "")).strip():
                gaps.append("criterion {} lacks an evidence location".format(label))

    checks = evidence.get("checks")
    if not isinstance(checks, list):
        gaps.append("checks must be an array")
    else:
        for index, check in enumerate(checks):
            label = (
                str(check.get("name", index + 1))
                if isinstance(check, dict)
                else str(index + 1)
            )
            if not isinstance(check, dict):
                gaps.append("check {} is not an object".format(label))
                continue
            if check.get("required") is not True:
                continue
            if check.get("exitCode") != 0:
                gaps.append("required check {} did not exit zero".format(label))
            if not str(check.get("location", "")).strip():
                gaps.append(
                    "required check {} lacks a raw evidence location".format(label)
                )
            if check.get("requiresExecutedTests") is True:
                count = check.get("executedTests")
                if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
                    gaps.append("required check {} has no executed tests".format(label))

    snapshots = evidence.get("snapshots", {})
    if not isinstance(snapshots, dict):
        gaps.append("snapshots must be an object")
    elif snapshots.get("required") not in {True, False}:
        gaps.append("snapshots.required must be explicit")
    elif snapshots.get("required") is True:
        for field in ("recorded", "inspected", "compared", "clean"):
            if snapshots.get(field) is not True:
                gaps.append("snapshot {} is not proven".format(field))
        if not str(snapshots.get("location", "")).strip():
            gaps.append("snapshot evidence lacks a location")

    runtime = evidence.get("runtime", {})
    if not isinstance(runtime, dict):
        gaps.append("runtime must be an object")
    elif runtime.get("required") not in {True, False}:
        gaps.append("runtime.required must be explicit")
    elif runtime.get("required") is True:
        if runtime.get("complete") is not True:
            gaps.append("runtime evidence is incomplete")
        for field in ("binary", "scenario", "device", "location"):
            if not str(runtime.get(field, "")).strip():
                gaps.append("runtime evidence lacks {}".format(field))
        if runtime.get("laneOwned") is not True:
            gaps.append("runtime evidence is not from an owned lane")

    apple_lane = evidence.get("appleLane", {})
    if not isinstance(apple_lane, dict):
        gaps.append("appleLane must be an object")
    elif apple_lane.get("required") not in {True, False}:
        gaps.append("appleLane.required must be explicit")
    elif apple_lane.get("required") is True and apple_lane.get("released") is not True:
        gaps.append("Apple verification lane remains leased")

    scope = evidence.get("scope", {})
    if not isinstance(scope, dict) or scope.get("reviewed") is not True:
        gaps.append("changed scope was not reviewed")
    elif scope.get("unrelatedChanges") is not False:
        gaps.append("changed scope contains unrelated work")

    notes = evidence.get("notes", {})
    if not isinstance(notes, dict) or notes.get("reviewed") is not True:
        gaps.append("implementation notes were not reviewed")
    elif not isinstance(notes.get("materialOmissions"), list):
        gaps.append("implementation notes must explicitly list material omissions")
    elif notes.get("materialOmissions"):
        gaps.append("implementation notes have material omissions")

    actions = evidence.get("actions")
    if not isinstance(actions, list):
        gaps.append("actions must be an array")
    else:
        for index, action in enumerate(actions):
            name = (
                str(action.get("name", index + 1))
                if isinstance(action, dict)
                else str(index + 1)
            )
            if not isinstance(action, dict):
                gaps.append("action {} is not an object".format(name))
                continue
            if action.get("required") is True and action.get("authorized") is not True:
                gaps.append("required action {} lacks authority".format(name))
            if action.get("required") is True and action.get("performed") is not True:
                gaps.append("required action {} was not performed".format(name))

    unauthorized = evidence.get("unauthorizedActions")
    if not isinstance(unauthorized, list):
        gaps.append("unauthorizedActions must be an array")
    elif unauthorized:
        gaps.append(
            "unauthorized actions were recorded: {}".format(
                ", ".join(map(str, unauthorized))
            )
        )

    assignments = state.get("assignments", [])
    if isinstance(assignments, list):
        unresolved = [
            str(item.get("agent"))
            for item in assignments
            if isinstance(item, dict)
            and item.get("ticket") == ticket_id
            and item.get("status") != "done"
        ]
        if unresolved:
            gaps.append(
                "ticket has unresolved assignments: {}".format(
                    ", ".join(sorted(unresolved))
                )
            )

    if include_assignment_errors:
        gaps.extend(assignment_errors(state))
    return unique(gaps)


def state_errors(state: Dict[str, Any]) -> List[str]:
    errors = graph_errors(state) + assignment_errors(state)
    for ticket in tickets_by_id(state).values():
        if ticket.get("phase") != "closed":
            continue
        ticket_id = str(ticket.get("id"))
        errors.extend(
            "closed ticket {}: {}".format(ticket_id, gap)
            for gap in closure_gaps(state, ticket_id, include_assignment_errors=False)
        )
    return unique(errors)


def frontier(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    tickets = tickets_by_id(state)
    ready = []
    for ticket in tickets.values():
        if ticket.get("phase") != "queued":
            continue
        if all(
            tickets[blocker].get("phase") == "closed"
            for blocker in ticket.get("blockers", [])
            if blocker in tickets
        ):
            ready.append(ticket)
    return sorted(ready, key=ticket_sort_key)


def recovered_state(state: Dict[str, Any], ticket_id: str) -> Dict[str, Any]:
    ticket = tickets_by_id(state).get(ticket_id)
    if ticket is None:
        raise WorkflowError("unknown ticket: {}".format(ticket_id))
    assignments = [
        assignment
        for assignment in state.get("assignments", [])
        if isinstance(assignment, dict) and assignment.get("ticket") == ticket_id
    ]
    return {
        "ticket": ticket_id,
        "phase": ticket.get("phase"),
        "repositoryStatus": ticket.get("repositoryStatus"),
        "completedAssignments": sorted(
            str(item.get("agent"))
            for item in assignments
            if item.get("status") == "done"
        ),
        "unresolvedAssignments": sorted(
            str(item.get("agent"))
            for item in assignments
            if item.get("status") != "done"
        ),
        "closureGaps": closure_gaps(state, ticket_id),
        "lastEvent": state.get("lastEvent"),
    }


def next_action(state: Dict[str, Any]) -> Dict[str, Any]:
    errors = state_errors(state)
    if errors:
        return {"action": "invalid_state", "errors": errors}

    active = [
        ticket
        for ticket in tickets_by_id(state).values()
        if ticket.get("phase") in ACTIVE_PHASES
    ]
    if active:
        ticket = active[0]
        ticket_id = str(ticket["id"])
        phase = str(ticket["phase"])
        if ticket.get("interrupted") is True:
            return {
                "action": "respawn_ticket_coordinator",
                "ticket": ticket_id,
                "recoveredState": recovered_state(state, ticket_id),
            }
        if phase == "coordinating":
            return {"action": "wait_ticket_coordinator", "ticket": ticket_id}
        if phase == "acceptance":
            return {"action": "spawn_acceptance_checker", "ticket": ticket_id}
        if phase == "gap":
            gaps = list(ticket.get("acceptanceGaps", [])) + closure_gaps(
                state, ticket_id
            )
            return {
                "action": "return_acceptance_gaps",
                "ticket": ticket_id,
                "gaps": unique(gaps),
            }
        gaps = closure_gaps(state, ticket_id)
        if gaps:
            return {"action": "reject_closure", "ticket": ticket_id, "gaps": gaps}
        return {"action": "close_ticket", "ticket": ticket_id}

    ready = frontier(state)
    if ready:
        return {"action": "spawn_ticket_coordinator", "ticket": str(ready[0]["id"])}

    tickets = list(tickets_by_id(state).values())
    if tickets and all(ticket.get("phase") == "closed" for ticket in tickets):
        return {"action": "run_complete"}

    remaining = []
    for ticket in sorted(tickets, key=ticket_sort_key):
        if ticket.get("phase") == "closed":
            continue
        remaining.append(
            {
                "ticket": str(ticket.get("id")),
                "phase": ticket.get("phase"),
                "reason": ticket.get("blockerReason", "waiting on unresolved blocker"),
            }
        )
    return {"action": "run_blocked", "tickets": remaining}


def transition(
    state: Dict[str, Any],
    ticket_id: str,
    target: str,
    actor: str,
    reason: str,
    repository_status: Optional[str],
) -> Dict[str, Any]:
    if not actor.strip():
        raise WorkflowError("actor must be non-empty", exit_code=3)
    errors = state_errors(state)
    if errors:
        raise WorkflowError("invalid state: {}".format("; ".join(errors)))
    ticket = tickets_by_id(state).get(ticket_id)
    if ticket is None:
        raise WorkflowError("unknown ticket: {}".format(ticket_id))
    current = str(ticket.get("phase"))
    if target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise WorkflowError(
            "invalid transition {} -> {} for {}".format(current, target, ticket_id),
            exit_code=3,
        )
    if target == "coordinating":
        ready = frontier(state)
        if current == "blocked":
            all_tickets = tickets_by_id(state)
            blockers_ready = all(
                all_tickets[blocker].get("phase") == "closed"
                for blocker in ticket.get("blockers", [])
                if blocker in all_tickets
            )
            if blockers_ready:
                ready.append(ticket)
                ready = sorted(ready, key=ticket_sort_key)
        if not ready or str(ready[0].get("id")) != ticket_id:
            raise WorkflowError(
                "ticket {} is not the next dependency-ready frontier ticket".format(
                    ticket_id
                ),
                exit_code=3,
            )
    if target == "blocked" and not reason.strip():
        raise WorkflowError("blocked transition requires a reason", exit_code=3)
    if target == "gap" and not reason.strip():
        raise WorkflowError("gap transition requires an acceptance reason", exit_code=3)
    if target == "closed":
        gaps = closure_gaps(state, ticket_id)
        if gaps:
            raise WorkflowError(
                "closure rejected: {}".format("; ".join(gaps)), exit_code=3
            )

    ticket["phase"] = target
    ticket["interrupted"] = False
    if repository_status is not None:
        if not repository_status.strip():
            raise WorkflowError("repository status cannot be empty", exit_code=3)
        ticket["repositoryStatus"] = repository_status
    if target == "blocked":
        ticket["blockerReason"] = reason
    else:
        ticket.pop("blockerReason", None)
    if target == "gap":
        ticket["acceptanceGaps"] = [reason]
    elif current == "gap":
        ticket.pop("acceptanceGaps", None)
    return {
        "type": "transition",
        "ticket": ticket_id,
        "from": current,
        "to": target,
        "actor": actor,
        "reason": reason,
        "repositoryStatus": ticket.get("repositoryStatus"),
    }


def mark_interrupted(
    state: Dict[str, Any], ticket_id: str, actor: str, reason: str
) -> Dict[str, Any]:
    if not actor.strip() or not reason.strip():
        raise WorkflowError(
            "interruption requires non-empty actor and reason", exit_code=3
        )
    errors = state_errors(state)
    if errors:
        raise WorkflowError("invalid state: {}".format("; ".join(errors)))
    ticket = tickets_by_id(state).get(ticket_id)
    if ticket is None:
        raise WorkflowError("unknown ticket: {}".format(ticket_id))
    if ticket.get("phase") not in ACTIVE_PHASES:
        raise WorkflowError("only an active ticket can be interrupted", exit_code=3)
    ticket["interrupted"] = True
    return {
        "type": "interrupted",
        "ticket": ticket_id,
        "phase": ticket.get("phase"),
        "actor": actor,
        "reason": reason,
    }


def event_path(
    state_path: Path, state: Dict[str, Any], override: Optional[str]
) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    configured = state.get("eventLog")
    if isinstance(configured, str) and configured.strip():
        candidate = Path(configured)
        return (
            candidate.resolve()
            if candidate.is_absolute()
            else (state_path.parent / candidate).resolve()
        )
    return state_path.with_suffix(".events.jsonl")


def append_event(
    path: Path, state: Dict[str, Any], event: Dict[str, Any]
) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    sequence = int(state.get("eventSequence", 0)) + 1
    enriched = dict(event)
    enriched["sequence"] = sequence
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(enriched, sort_keys=True, separators=(",", ":")))
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    state["eventSequence"] = sequence
    state["lastEvent"] = enriched
    return enriched


def unique(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def emit(payload: Dict[str, Any], pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument(
        "--pretty",
        action="store_true",
        help="pretty-print JSON instead of compact output",
    )
    commands = root.add_subparsers(dest="command", required=True)

    validate_parser = commands.add_parser(
        "validate", help="validate graph, assignments, and optional ticket closure"
    )
    validate_parser.add_argument("--state", required=True)
    validate_parser.add_argument("--closure", metavar="TICKET")

    next_parser = commands.add_parser("next", help="derive the next host action")
    next_parser.add_argument("--state", required=True)

    recover_parser = commands.add_parser(
        "recover", help="derive persistent recovery state for a ticket"
    )
    recover_parser.add_argument("--state", required=True)
    recover_parser.add_argument("--ticket", required=True)

    transition_parser = commands.add_parser(
        "transition", help="apply an allowed ticket phase transition"
    )
    transition_parser.add_argument("--state", required=True)
    transition_parser.add_argument("--ticket", required=True)
    transition_parser.add_argument("--to", choices=sorted(PHASES), required=True)
    transition_parser.add_argument("--actor", required=True)
    transition_parser.add_argument("--reason", default="")
    transition_parser.add_argument("--repository-status")
    transition_parser.add_argument("--events")

    interrupt_parser = commands.add_parser(
        "interrupt", help="mark an active ticket for deterministic recovery"
    )
    interrupt_parser.add_argument("--state", required=True)
    interrupt_parser.add_argument("--ticket", required=True)
    interrupt_parser.add_argument("--actor", required=True)
    interrupt_parser.add_argument("--reason", required=True)
    interrupt_parser.add_argument("--events")
    return root


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    state_path = Path(args.state).expanduser().resolve()
    try:
        state = read_state(state_path)
        if args.command == "validate":
            errors = state_errors(state)
            closure = closure_gaps(state, args.closure) if args.closure else []
            payload = {
                "valid": not errors and not closure,
                "structurallyValid": not errors,
                "closureChecked": args.closure is not None,
                "closureValid": None if args.closure is None else not closure,
                "errors": errors,
                "closureGaps": closure,
            }
            emit(payload, args.pretty)
            return 0 if payload["valid"] else 2
        if args.command == "next":
            payload = next_action(state)
            emit(payload, args.pretty)
            return 2 if payload["action"] == "invalid_state" else 0
        if args.command == "recover":
            errors = state_errors(state)
            if errors:
                raise WorkflowError("invalid state: {}".format("; ".join(errors)))
            emit(recovered_state(state, args.ticket), args.pretty)
            return 0

        original = copy.deepcopy(state)
        if args.command == "transition":
            event = transition(
                state,
                args.ticket,
                args.to,
                args.actor,
                args.reason,
                args.repository_status,
            )
        else:
            event = mark_interrupted(state, args.ticket, args.actor, args.reason)
        enriched = append_event(
            event_path(state_path, state, args.events), state, event
        )
        write_state(state_path, state)
        emit(
            {
                "changed": state != original,
                "event": enriched,
                "next": next_action(state),
            },
            args.pretty,
        )
        return 0
    except WorkflowError as error:
        emit({"error": str(error)}, getattr(args, "pretty", False))
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
