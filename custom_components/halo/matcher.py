"""State matching with per-mood tolerance / ignore rules.

Borrowed ideas:
- stateful_scenes: numeric tolerance, ignore attributes, ignore unavailable.
- scene_state: exact compare of only attrs the scene stores + per-attr tolerance,
  mismatched_entities reporting.
"""
from __future__ import annotations

from typing import Any

# Metadata attributes that can never meaningfully verify lighting output.
# friendly_name changes on renames (including HA device renames that
# propagate), while the light itself is untouched. Comparing it turns every
# rename into a permanent mismatch, so it is always skipped. icon is the
# same kind of device metadata (icon changes, custom card icons), never
# light output.
ALWAYS_IGNORED_ATTRS = frozenset({"friendly_name", "icon"})


def _num_close(a: Any, b: Any, tol: float) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def _seq_close(a: Any, b: Any, tol: float) -> bool:
    # rgb_color / xy / hs tuples: every channel within tolerance
    if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)):
        return a == b
    if len(a) != len(b):
        return False
    try:
        return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))
    except (TypeError, ValueError):
        return list(a) == list(b)


def entity_matches(
    expected: dict[str, Any],
    actual_state: str | None,
    actual_attrs: dict[str, Any],
    *,
    tolerance: float = 1.0,
    ignore_attrs: list[str] | set[str] | tuple = (),
    ignore_unavailable: bool = True,
) -> tuple[bool, bool]:
    """Compare one entity.

    Returns (matches, unknown). unknown=True means the entity is
    unavailable/missing but ignore_unavailable is on, so it neither
    matches nor mismatches (mirrors scene_state 'unknown' handling).
    """
    ignore = set(ignore_attrs or ()) | ALWAYS_IGNORED_ATTRS
    exp_state = expected.get("state")

    if actual_state in (None, "unavailable", "unknown", ""):
        if ignore_unavailable:
            return True, True
        return False, False

    if exp_state is not None and actual_state != exp_state:
        # 'off' scenes store state off; lights report off without attrs.
        return False, False

    for key, exp_val in expected.items():
        if key == "state" or key in ignore:
            continue
        act_val = actual_attrs.get(key)
        if act_val is None:
            # Device doesn't report this attr (e.g. brightness: null on
            # some MQTT optimistic lights). Treat like unavailable:
            # skip when ignoring unavailable, else mismatch.
            if ignore_unavailable:
                continue
            return False, False
        if isinstance(exp_val, (list, tuple)):
            if not _seq_close(exp_val, act_val, tolerance):
                return False, False
        elif isinstance(exp_val, (int, float)):
            if not _num_close(exp_val, act_val, tolerance):
                return False, False
        else:
            if exp_val != act_val:
                return False, False
    return True, False


def diff_entity(
    expected: dict[str, Any],
    actual_state: str | None,
    actual_attrs: dict[str, Any],
    *,
    tolerance: float = 1.0,
    ignore_attrs: list[str] | set[str] | tuple = (),
    ignore_unavailable: bool = True,
) -> dict[str, list]:
    """Per-attribute differences for one entity.

    Returns {attr: [expected, actual]} for every compared value that
    differs. Empty means match (or unknown-but-ignored). Mirrors
    entity_matches exactly, so the two can never disagree.
    """
    ignore = set(ignore_attrs or ()) | ALWAYS_IGNORED_ATTRS
    diffs: dict[str, list] = {}
    exp_state = expected.get("state")

    if actual_state in (None, "unavailable", "unknown", ""):
        if ignore_unavailable:
            return {}
        return {"state": [exp_state, actual_state]}

    if exp_state is not None and actual_state != exp_state:
        # State mismatch dominates; attrs are meaningless across on/off.
        return {"state": [exp_state, actual_state]}

    for key, exp_val in expected.items():
        if key == "state" or key in ignore:
            continue
        act_val = actual_attrs.get(key)
        if act_val is None:
            if ignore_unavailable:
                continue
            diffs[key] = [exp_val, None]
            continue
        if isinstance(exp_val, (list, tuple)):
            if not _seq_close(exp_val, act_val, tolerance):
                diffs[key] = [list(exp_val), act_val]
        elif isinstance(exp_val, (int, float)):
            if not _num_close(exp_val, act_val, tolerance):
                diffs[key] = [exp_val, act_val]
        else:
            if exp_val != act_val:
                diffs[key] = [exp_val, act_val]
    return diffs


def score_snapshot(
    expected_map: dict[str, dict[str, Any]],
    states: dict[str, tuple[str | None, dict[str, Any]]],
    *,
    tolerance: float = 1.0,
    ignore_attrs: list[str] | set[str] | tuple = (),
    ignore_unavailable: bool = True,
) -> float:
    """0-100 similarity where on/off state outweighs all attributes combined.

    Counts state agreements and attribute agreements separately: one state
    hit scores a full point while every attribute of the whole snapshot
    shares less than one point, so any state agreement beats any attribute
    combination, and attributes only break state ties. Unknown (skipped)
    entities count for neither side, mirroring snapshot_matches.
    """
    ignore = set(ignore_attrs or ()) | ALWAYS_IGNORED_ATTRS
    state_hits = state_total = attr_hits = attr_total = 0
    for entity_id, expected in expected_map.items():
        actual = states.get(entity_id)
        if actual is None or actual[0] in (None, "unavailable", "unknown", ""):
            if ignore_unavailable:
                continue
            # Counted as a state miss with nothing comparable (mirrors the
            # mismatch snapshot_matches reports here).
            state_total += 1
            continue
        act_state, act_attrs = actual
        exp_state = expected.get("state")
        state_total += 1
        if exp_state is None or act_state == exp_state:
            state_hits += 1
        for key, exp_val in expected.items():
            if key == "state" or key in ignore:
                continue
            attr_total += 1
            act_val = act_attrs.get(key)
            if act_val is None:
                if ignore_unavailable:
                    attr_total -= 1
                    continue
                continue  # in total, not in hits: a miss
            if isinstance(exp_val, (list, tuple)):
                if _seq_close(exp_val, act_val, tolerance):
                    attr_hits += 1
            elif isinstance(exp_val, (int, float)):
                if _num_close(exp_val, act_val, tolerance):
                    attr_hits += 1
            elif exp_val == act_val:
                attr_hits += 1
    if state_total == 0:
        return 0.0
    return 100 * (state_hits + attr_hits / (attr_total + 1)) / (
        state_total + attr_total / (attr_total + 1)
    )


def diff_snapshot(
    expected_map: dict[str, dict[str, Any]],
    states: dict[str, tuple[str | None, dict[str, Any]]],
    *,
    tolerance: float = 1.0,
    ignore_attrs: list[str] | set[str] | tuple = (),
    ignore_unavailable: bool = True,
) -> dict[str, dict[str, list]]:
    """Per-entity diffs for a snapshot: {entity_id: {attr: [exp, act]}}."""
    out: dict[str, dict[str, list]] = {}
    for entity_id, expected in expected_map.items():
        actual = states.get(entity_id)
        if actual is None:
            if not ignore_unavailable:
                out[entity_id] = {"state": [expected.get("state"), None]}
            continue
        diff = diff_entity(
            expected,
            actual[0],
            actual[1],
            tolerance=tolerance,
            ignore_attrs=ignore_attrs,
            ignore_unavailable=ignore_unavailable,
        )
        if diff:
            out[entity_id] = diff
    return out


def snapshot_matches(
    expected_map: dict[str, dict[str, Any]],
    states: dict[str, tuple[str | None, dict[str, Any]]],
    *,
    tolerance: float = 1.0,
    ignore_attrs: list[str] | set[str] | tuple = (),
    ignore_unavailable: bool = True,
) -> tuple[bool, list[str], bool]:
    """Check a full (mood, preset) snapshot.

    states: entity_id -> (state, attrs).
    Returns (all_match, mismatched_entities, any_unknown).
    """
    mismatched: list[str] = []
    any_unknown = False
    for entity_id, expected in expected_map.items():
        actual = states.get(entity_id)
        if actual is None:
            if ignore_unavailable:
                any_unknown = True
                continue
            mismatched.append(entity_id)
            continue
        ok, unknown = entity_matches(
            expected,
            actual[0],
            actual[1],
            tolerance=tolerance,
            ignore_attrs=ignore_attrs,
            ignore_unavailable=ignore_unavailable,
        )
        if unknown:
            any_unknown = True
        if not ok:
            mismatched.append(entity_id)
    return (len(mismatched) == 0, mismatched, any_unknown)
