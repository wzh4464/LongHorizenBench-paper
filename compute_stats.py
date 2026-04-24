"""Recompute headline numbers for the paper from reports/eval_scores_v2_wide.csv.

The paper's Table 1 uses a *lenient-fail* majority rule (PASS if >=3 of 4 judges
agree; else FAIL if >=2 of 4 judges vote FAIL; else PARTIAL).  A strict rule
(>=3 FAIL) gives the same PASS counts but redistributes PARTIAL/FAIL.
"""
import csv
from collections import Counter, defaultdict

CSV = "reports/eval_scores_v2_wide.csv"


def family(task: str) -> str:
    if task.startswith("C"): return "CANN"
    if task.startswith("M"): return "MindSpeed"
    if task.startswith("K"): return "Kubernetes"
    if task.startswith("T"): return "CapBench"
    return "?"


def majority_lenient(row) -> str:
    """PASS >=3 PASS votes; FAIL >=2 FAIL votes; else PARTIAL. (Matches Table 1.)"""
    c = __import__("collections").Counter(
        row[k] for k in ("claude_verdict", "codex_verdict", "cursor_verdict", "glm_verdict") if row.get(k)
    )
    if c.get("PASS", 0) >= 3: return "PASS"
    if c.get("FAIL", 0) >= 2: return "FAIL"
    return "PARTIAL"


def main():
    import csv, collections
    rows = list(csv.DictReader(open("reports/eval_scores_v2_wide.csv")))
    print(f"Total runs: {len(rows)}")

    by_agent = collections.defaultdict(collections.Counter)
    for r in rows:
        by_agent[r["agent"]][majority_lenient(r)] += 1

    print(f"{'Agent':30s} {'PASS':>5} {'PART':>5} {'FAIL':>5}")
    for a in sorted(by_agent):
        c = by_agent[a]
        n = sum(c.values())
        print(f"  {a:30s} {c['PASS']:>5} {c['PARTIAL']:>5} {c['FAIL']:>5}   (n={n})")


def majority_lenient(row) -> str:
    import collections
    c = collections.Counter(row[k] for k in ("claude_verdict", "codex_verdict", "cursor_verdict", "glm_verdict") if row[k])
    if c.get("PASS", 0) >= 3: return "PASS"
    if c.get("FAIL", 0) >= 2: return "FAIL"
    return "PARTIAL"


if __name__ == "__main__":
    main()
