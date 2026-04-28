"""Recompute headline numbers from the evaluator CSV.

By default this script reads the parent workspace CSV because `paper2` is a
submodule inside the benchmark repository:

    python3 compute_stats.py
    python3 compute_stats.py ../reports/eval_scores_v2_long.csv
"""

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_CANDIDATES = (
    Path("../reports/eval_scores_v2_long.csv"),
    Path("reports/eval_scores_v2_long.csv"),
)


def family(task: str) -> str:
    if task.startswith("C"):
        return "CANN"
    if task.startswith("M"):
        return "MindSpeed"
    if task.startswith("K"):
        return "Kubernetes"
    if task.startswith("T"):
        return "CapBench"
    return "?"


def majority(verdicts: list[str]) -> str:
    counts = Counter(verdicts)
    if counts["PASS"] >= 3:
        return "PASS"
    if counts["FAIL"] >= 2:
        return "FAIL"
    return "PARTIAL"


def failure_signature(run: dict[str, object]) -> str:
    """Assign the root-cause signature used in Section 5."""
    if run["verdict"] == "PASS":
        return "pass"
    if float(run["mean_a"]) < 2:
        return "semantic_failure"
    if float(run["mean_b"]) < 2:
        return "coverage_gap"
    if float(run["mean_c"]) < 2:
        return "behavior_mismatch"
    return "borderline_partial"


def load_rows(path: Path) -> list[dict[str, str]]:
    rows = list(csv.DictReader(path.open()))
    for row in rows:
        if row["evaluator"] == "opencode-glm-5.1":
            row["evaluator"] = "glm"
    return rows


def resolve_csv() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    for candidate in DEFAULT_CANDIDATES:
        if candidate.exists():
            return candidate
    raise SystemExit("Could not find eval_scores_v2_long.csv")


def build_runs(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            row["task"],
            row["agent"],
            row["prompt_variant"],
            row["complexity"],
            row["dir"],
        )
        grouped[key].append(row)

    runs = []
    for (task, agent, prompt, complexity, run_dir), group in grouped.items():
        mean_a = sum(float(row["score_a"]) for row in group) / len(group)
        mean_b = sum(float(row["score_b"]) for row in group) / len(group)
        mean_c = sum(float(row["score_c"]) for row in group) / len(group)
        mean15 = sum(
            float(row["score_a"]) + float(row["score_b"]) + float(row["score_c"])
            for row in group
        ) / len(group)
        run = {
            "task": task,
            "agent": agent,
            "prompt": prompt,
            "complexity": complexity,
            "dir": run_dir,
            "family": family(task),
            "verdict": majority([row["verdict"] for row in group]),
            "mean_a": mean_a,
            "mean_b": mean_b,
            "mean_c": mean_c,
            "mean15": mean15,
        }
        run["failure_signature"] = failure_signature(run)
        runs.append(run)
    return runs


def print_counter(title: str, runs: list[dict[str, object]], key: str) -> None:
    print(f"\n{title}")
    for value in sorted({run[key] for run in runs}):
        subset = [run for run in runs if run[key] == value]
        counts = Counter(run["verdict"] for run in subset)
        pass_pct = counts["PASS"] / len(subset) * 100
        mean15 = sum(float(run["mean15"]) for run in subset) / len(subset)
        print(
            f"{value:18s} n={len(subset):3d} "
            f"PASS={counts['PASS']:2d} PARTIAL={counts['PARTIAL']:3d} "
            f"FAIL={counts['FAIL']:3d} PASS%={pass_pct:4.1f} mean15={mean15:4.2f}"
        )


def corpus(task: str) -> str:
    if task.startswith("T"):
        return "main"
    return "calibration"


def print_failure_signatures(runs: list[dict[str, object]]) -> None:
    non_pass = [run for run in runs if run["verdict"] != "PASS"]
    labels = (
        "semantic_failure",
        "coverage_gap",
        "borderline_partial",
        "behavior_mismatch",
    )

    print("\nFailure signatures")
    counts = Counter(run["failure_signature"] for run in non_pass)
    for label in labels:
        print(f"{label:22s} {counts[label]:3d} {counts[label] / len(non_pass) * 100:4.1f}%")

    print("\nFailure signatures by agent")
    for agent in sorted({run["agent"] for run in non_pass}):
        subset = [run for run in non_pass if run["agent"] == agent]
        counts = Counter(run["failure_signature"] for run in subset)
        values = " ".join(f"{label}={counts[label]:3d}" for label in labels)
        print(f"{agent:18s} n={len(subset):3d} {values}")

    print("\nFailure signatures by family")
    for task_family in ("CANN", "MindSpeed", "Kubernetes", "CapBench"):
        subset = [run for run in non_pass if run["family"] == task_family]
        counts = Counter(run["failure_signature"] for run in subset)
        values = " ".join(f"{label}={counts[label]:3d}" for label in labels)
        print(f"{task_family:18s} n={len(subset):3d} {values}")


def main() -> None:
    csv_path = resolve_csv()
    rows = load_rows(csv_path)
    runs = build_runs(rows)

    print(f"CSV: {csv_path}")
    print(f"Evaluator rows: {len(rows)}")
    print(f"Runs: {len(runs)}")
    print(f"Overall: {Counter(run['verdict'] for run in runs)}")

    print_counter("By agent", runs, "agent")
    print_counter("By family", runs, "family")
    print_counter("By complexity", runs, "complexity")
    print_failure_signatures(runs)

    print("\nBy agent x prompt")
    for agent in sorted({run["agent"] for run in runs}):
        for prompt in ("short", "long"):
            subset = [
                run for run in runs
                if run["agent"] == agent and run["prompt"] == prompt
            ]
            counts = Counter(run["verdict"] for run in subset)
            mean15 = sum(float(run["mean15"]) for run in subset) / len(subset)
            print(
                f"{agent:18s} {prompt:5s} "
                f"PASS={counts['PASS']:2d}/{len(subset)} "
                f"PASS%={counts['PASS'] / len(subset) * 100:4.1f} "
                f"mean15={mean15:4.2f}"
            )

    print("\nPASS runs")
    for run in sorted(
        (run for run in runs if run["verdict"] == "PASS"),
        key=lambda r: (str(r["task"]), str(r["agent"]), str(r["prompt"])),
    ):
        print(f"{run['task']:4s} {run['agent']:18s} {run['prompt']}")

    # --- Calibration vs Main corpus split ---
    main_runs = [run for run in runs if corpus(str(run["task"])) == "main"]
    cal_runs = [run for run in runs if corpus(str(run["task"])) == "calibration"]
    main_no_t10 = [run for run in main_runs if run["task"] != "T10"]

    print("\n" + "=" * 60)
    print("CALIBRATION vs MAIN CORPUS SPLIT")
    print("=" * 60)

    for label, subset in [
        ("Main corpus (T01-T50)", main_runs),
        ("Main excl T10", main_no_t10),
        ("Calibration (C/K/M)", cal_runs),
    ]:
        counts = Counter(run["verdict"] for run in subset)
        pass_pct = counts["PASS"] / len(subset) * 100 if subset else 0
        mean15 = sum(float(run["mean15"]) for run in subset) / len(subset) if subset else 0
        print(
            f"\n{label}: n={len(subset)} "
            f"PASS={counts['PASS']} PARTIAL={counts['PARTIAL']} FAIL={counts['FAIL']} "
            f"PASS%={pass_pct:.1f} mean15={mean15:.2f}"
        )

    print_counter("\nMain corpus by agent", main_runs, "agent")
    print_counter("Main corpus by agent (excl T10)", main_no_t10, "agent")
    print_counter("Calibration by agent", cal_runs, "agent")
    print_counter("Calibration by family", cal_runs, "family")

    print("\nMain corpus: agent x prompt")
    for agent in sorted({run["agent"] for run in main_runs}):
        for prompt in ("short", "long"):
            subset = [
                run for run in main_runs
                if run["agent"] == agent and run["prompt"] == prompt
            ]
            if not subset:
                continue
            counts = Counter(run["verdict"] for run in subset)
            mean15 = sum(float(run["mean15"]) for run in subset) / len(subset)
            print(
                f"{agent:18s} {prompt:5s} "
                f"PASS={counts['PASS']:2d}/{len(subset)} "
                f"PASS%={counts['PASS'] / len(subset) * 100:4.1f} "
                f"mean15={mean15:4.2f}"
            )

    print("\nMain corpus failure signatures")
    non_pass_main = [run for run in main_runs if run["verdict"] != "PASS"]
    labels = ("semantic_failure", "coverage_gap", "borderline_partial", "behavior_mismatch")
    counts = Counter(run["failure_signature"] for run in non_pass_main)
    for label in labels:
        print(f"{label:22s} {counts[label]:3d} {counts[label] / len(non_pass_main) * 100:4.1f}%")

    print("\nMain corpus failure signatures by agent")
    for agent in sorted({run["agent"] for run in non_pass_main}):
        subset = [run for run in non_pass_main if run["agent"] == agent]
        counts = Counter(run["failure_signature"] for run in subset)
        values = " ".join(f"{label}={counts[label]:3d}" for label in labels)
        print(f"{agent:18s} n={len(subset):3d} {values}")


if __name__ == "__main__":
    main()
