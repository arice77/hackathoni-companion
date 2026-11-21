"""Replay the frozen planner cases against one or both Sarvam chat models."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion.contracts import Control, Snapshot
from companion.planner_sarvam import MODEL_ENDPOINTS, SarvamPlanner
from companion.validator import MAX_SNAPSHOT_AGE_S, validate
from companion.voice import sarvam

FIXTURES = ROOT / "tests" / "fixtures" / "planner"
MAX_CALLS = 156


def _snapshot(name: str, record: dict, stale: bool) -> Snapshot:
    controls = tuple(
        Control(frame=(20.0, 20.0 + i * 30, 240.0, 24.0), **row)
        for i, row in enumerate(record["controls"])
    )
    age = MAX_SNAPSHOT_AGE_S + 1 if stale else 0
    frame = (0, 0, 600, 40 + len(controls) * 30)
    return Snapshot(
        snapshot_id=name,
        taken_at=time.time() - age,
        app_bundle_id=f"fixture.{record['origin']}",
        app_pid=0,
        window_title=record.get("host", name),
        window_frame=frame,
        controls=controls,
        viewport=frame if record["origin"] in {"safari-reader", "public-safari-reader", "kseb-probe-replay"} else None,
    )


def _case(model: str, case: dict, screen: dict) -> dict:
    planner = SarvamPlanner(case["task"], model=model, log_calls=False)
    snap = _snapshot(case["screen"], screen, case.get("stale", False))
    decision = planner.decide(case["question"], snap)
    cold_calls = len(planner.calls)
    cold_valid, cold_reason = validate(decision, snap)

    remapped_ids = {control.id: f"warm-{i}" for i, control in enumerate(snap.controls)}
    warm = replace(
        snap, snapshot_id=f"{snap.snapshot_id}-warm", taken_at=time.time(),
        controls=tuple(replace(c, id=remapped_ids[c.id]) for c in reversed(snap.controls)),
    )
    cached = planner.decide(case["question"], warm)
    cache_valid, cache_reason = validate(cached, warm)
    cache_ok = (
        cold_calls <= 1
        and len(planner.calls) == cold_calls
        and cache_valid
        and cached == replace(
            decision, snapshot_id=warm.snapshot_id, control_id=remapped_ids.get(decision.control_id)
        )
    )
    expected = (case["kind"], case["control_id"])
    actual = (decision.kind, decision.control_id)
    orientation_ok = None
    if prefix := case.get("orientation_en"):
        target = snap.control(case["control_id"])
        quoted_label = f"‘{target.label}’"
        orientation_ok = (
            actual == expected
            and decision.instruction_en.startswith(prefix)
            and quoted_label in decision.instruction_en
            and quoted_label in decision.instruction
        )
    choice_guidance_ok = None
    if fragments := case.get("instruction_contains"):
        choice_guidance_ok = actual == expected and all(
            phrase in getattr(decision, attribute) for attribute, phrases in fragments.items() for phrase in phrases
        )
    return {
        "id": case["id"],
        "origin": screen["origin"],
        "question_form": case["question_form"],
        "expected": {"kind": expected[0], "control_id": expected[1]},
        "actual": asdict(decision),
        "correct": actual == expected,
        "orientation_ok": orientation_ok,
        "choice_guidance_ok": choice_guidance_ok,
        "decision_path": "provider" if cold_calls else "local",
        "cold_validator": {"valid": cold_valid, "reason": cold_reason},
        "stale_case": case.get("stale", False),
        "cache_ok": cache_ok,
        "cache_validator": {"valid": cache_valid, "reason": cache_reason},
        "calls": [asdict(call) for call in planner.calls],
    }


def _summary(rows: list[dict], total: int) -> dict:
    calls = [call for row in rows for call in row["calls"]]
    samples = [call["latency_ms"] for call in calls]
    invalid = sum(call["outcome"] == "unknown_id" for call in calls)
    malformed = sum(call["outcome"] == "malformed" for call in calls)
    correct = sum(row["correct"] for row in rows)
    orientations = [row["orientation_ok"] for row in rows if row["orientation_ok"] is not None]
    choice_guidance = [row["choice_guidance_ok"] for row in rows if row["choice_guidance_ok"] is not None]
    return {
        "correct": correct,
        "cases": len(rows),
        "expected_cases": total,
        "met_target": (
            len(rows) == total and correct * 17 >= total * 15 and invalid == malformed == 0
            and all(orientations) and all(choice_guidance)
        ),
        "calls": len(calls),
        "local_decisions": sum(row["decision_path"] == "local" for row in rows),
        "invalid_ids": invalid,
        "invalid_id_rate": invalid / len(calls) if calls else None,
        "malformed_replies": malformed,
        "orientations_correct": sum(orientations),
        "orientation_cases": len(orientations),
        "choice_guidance_correct": sum(choice_guidance),
        "choice_guidance_cases": len(choice_guidance),
        "label_fallbacks": sum(call["outcome"] == "local_label_fallback" for call in calls),
        "p50_ms": statistics.median(samples) if samples else None,
        "p95_ms": statistics.quantiles(samples, n=100, method="inclusive")[94] if len(samples) > 1
        else next(iter(samples), None),
        "warm_rebinds": sum(row["cache_ok"] for row in rows),
        "intentional_stale_rejected": sum(
            row["stale_case"] and row["cold_validator"]["reason"] == "snapshot is stale" for row in rows
        ),
        "cold_expired": sum(
            not row["stale_case"] and row["cold_validator"]["reason"] == "snapshot is stale" for row in rows
        ),
    }


def _run(model: str, cases: list[dict], screens: dict) -> tuple[dict, bool]:
    rows = []
    stop_all = False
    for case in cases:
        row = _case(model, case, screens[case["screen"]])
        rows.append(row)
        call = next(iter(row["calls"]), {})
        outcome = call.get("outcome", "local")
        actual = row["actual"]
        mark = "pass" if row["correct"] else "fail"
        evidence = "live" if call else "local"
        print(f"[{evidence}] {model} {row['id']} {mark} · {actual['kind']}/{actual['control_id']} · {outcome}",
              flush=True)
        status = call.get("http_status")
        stop_all = status in (402, 403) or actual["instruction_en"] == "BLOCKED: no SARVAM_API_KEY"
        if stop_all or status in (400, 404):
            break
    return {"model": model, "endpoint": MODEL_ENDPOINTS[model], "summary": _summary(rows, len(cases)),
            "cases": rows}, stop_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=MODEL_ENDPOINTS, help="Evaluate one model (default compares both)")
    args = parser.parse_args(argv)
    cases = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))
    screens = json.loads((FIXTURES / "screens.json").read_text(encoding="utf-8"))
    models = (args.model,) if args.model else tuple(MODEL_ENDPOINTS)
    limit = len(cases) * len(models)
    if not 0 < limit <= MAX_CALLS:
        parser.error(f"Evaluation requires {limit} calls. Limit is {MAX_CALLS}.")
    try:
        sarvam._load_api_key()
    except sarvam.SarvamMissingKeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    except sarvam.SarvamError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    results = []
    for model in models:
        result, stop = _run(model, cases, screens)
        results.append(result)
        if stop:
            break
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    report = ROOT / "runs" / f"sarvam-planner-eval-{stamp}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"evidence": "live", "calls_planned": limit, "models": results},
                                 indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for result in results:
        print(f"[live] {result['model']} {json.dumps(result['summary'])}")
    print(f"[live] Report {report}")
    return int(
        len(results) != len(models)
        or any(
            not result["summary"]["met_target"]
            or result["summary"]["warm_rebinds"] != len(cases)
            or result["summary"]["intentional_stale_rejected"] != sum(bool(case.get("stale")) for case in cases)
            for result in results
        )
    )


if __name__ == "__main__":
    sys.exit(main())
