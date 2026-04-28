#!/usr/bin/env python3
"""Leave-one-family-out judge bias analysis for the ASE paper."""
import csv
from collections import defaultdict

CSV = "../reports/eval_scores_v2_long.csv"

AGENT_TO_FAMILY = {
    "claude-opus-max": "claude",
    "codex-gpt-5_4": "codex",
    "cursor-composer2": "cursor",
    "opencode-glm51": "glm",
}

EVALUATOR_FAMILY = {
    "claude": "claude",
    "codex": "codex",
    "cursor": "cursor",
    "glm": "glm",
    "opencode-glm-5.1": "glm",
}

def majority_verdict(verdicts):
    counts = defaultdict(int)
    for v in verdicts:
        counts[v] += 1
    for label in ["FAIL", "PARTIAL", "PASS"]:
        if counts[label] >= 3:
            return label
    if counts["PASS"] >= 2 and counts["PARTIAL"] >= 2:
        return "PARTIAL"
    if counts["FAIL"] >= 2:
        return "FAIL"
    return "PARTIAL"

rows = []
with open(CSV) as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

runs = defaultdict(list)
for r in rows:
    key = (r["task"], r["agent"], r["prompt_variant"])
    runs[key].append(r)

print("=== Leave-One-Family-Out Analysis ===\n")
print("For each agent, compare headline verdict using all 4 judges vs. excluding the same-family judge.\n")

changed = 0
total = 0
agent_stats = defaultdict(lambda: {"all_pass": 0, "excl_pass": 0, "total": 0,
                                    "all_mean": 0.0, "excl_mean": 0.0})

for key, evals in runs.items():
    task, agent, prompt = key
    agent_family = AGENT_TO_FAMILY.get(agent)
    if not agent_family:
        continue

    all_verdicts = [e["verdict"] for e in evals]
    all_scores = [float(e["score_a"]) + float(e["score_b"]) + float(e["score_c"]) for e in evals]

    cross_verdicts = [e["verdict"] for e in evals if EVALUATOR_FAMILY[e["evaluator"]] != agent_family]
    cross_scores = [float(e["score_a"]) + float(e["score_b"]) + float(e["score_c"])
                    for e in evals if EVALUATOR_FAMILY[e["evaluator"]] != agent_family]

    v_all = majority_verdict(all_verdicts)
    v_cross = majority_verdict(cross_verdicts)

    mean_all = sum(all_scores) / len(all_scores)
    mean_cross = sum(cross_scores) / len(cross_scores) if cross_scores else 0

    total += 1
    if v_all != v_cross:
        changed += 1

    s = agent_stats[agent]
    s["total"] += 1
    s["all_pass"] += (v_all == "PASS")
    s["excl_pass"] += (v_cross == "PASS")
    s["all_mean"] += mean_all
    s["excl_mean"] += mean_cross

print(f"{'Agent':<25} {'N':>4} {'All-4 SE-PASS':>14} {'Excl-self SE-PASS':>18} {'All-4 Mean':>11} {'Excl-self Mean':>14} {'Δ Mean':>8}")
print("-" * 100)
for agent in sorted(agent_stats):
    s = agent_stats[agent]
    n = s["total"]
    print(f"{agent:<25} {n:>4} {s['all_pass']:>14} {s['excl_pass']:>18} "
          f"{s['all_mean']/n:>11.2f} {s['excl_mean']/n:>14.2f} {(s['excl_mean']-s['all_mean'])/n:>+8.2f}")

print(f"\nVerdict changes when excluding same-family judge: {changed}/{total} ({100*changed/total:.1f}%)")

print("\n=== Same-Family vs Cross-Family Score Gap ===\n")
print(f"{'Agent':<25} {'Self-judge Mean':>15} {'Cross-judge Mean':>16} {'Gap':>8}")
print("-" * 70)

for agent in sorted(AGENT_TO_FAMILY):
    family = AGENT_TO_FAMILY[agent]
    self_scores = []
    cross_scores = []
    for r in rows:
        if r["agent"] != agent:
            continue
        score = float(r["score_a"]) + float(r["score_b"]) + float(r["score_c"])
        if EVALUATOR_FAMILY[r["evaluator"]] == family:
            self_scores.append(score)
        else:
            cross_scores.append(score)

    if self_scores and cross_scores:
        ms = sum(self_scores) / len(self_scores)
        mc = sum(cross_scores) / len(cross_scores)
        print(f"{agent:<25} {ms:>15.2f} {mc:>16.2f} {ms-mc:>+8.2f}")
