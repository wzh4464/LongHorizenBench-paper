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
        mean15 = sum(
            float(row["score_a"]) + float(row["score_b"]) + float(row["score_c"])
            for row in group
        ) / len(group)
        runs.append(
            {
                "task": task,
                "agent": agent,
                "prompt": prompt,
                "complexity": complexity,
                "dir": run_dir,
                "family": family(task),
                "verdict": majority([row["verdict"] for row in group]),
                "mean15": mean15,
            }
        )
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


if __name__ == "__main__":
    main()
