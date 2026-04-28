#!/usr/bin/env python3
"""Generate TikZ coordinate data for the capability-cliff figure."""
import csv, os
from collections import defaultdict

CSV = "../reports/eval_scores_v2_long.csv"
BASE = "../base_repo"

# 1. Per-task mean composite score (A+B+C, averaged across all agents/prompts/evaluators)
scores = defaultdict(list)
with open(CSV) as f:
    for r in csv.DictReader(f):
        s = float(r["score_a"]) + float(r["score_b"]) + float(r["score_c"])
        scores[r["task"]].append(s)

task_mean = {t: sum(v)/len(v) for t, v in scores.items()}

# 2. GT file counts
gt_files = {}
for entry in os.listdir(BASE):
    path = os.path.join(BASE, entry, "eval", "gt_files.txt")
    if os.path.isfile(path):
        with open(path) as f:
            gt_files[entry] = sum(1 for _ in f)

# 3. Merge and sort by GT files ascending
tasks = sorted(set(task_mean) & set(gt_files), key=lambda t: (gt_files[t], t))

K_TASKS = {"K1", "K2", "K3", "K4"}

print("% task, gt_files, mean_score, is_k, is_t10")
print("% Sorted by GT files ascending")
print()
print("% TikZ coordinates for main bar chart (non-K, non-T10):")
print("\\addplot coordinates {")
for i, t in enumerate(tasks):
    if t not in K_TASKS and t != "T10":
        print(f"  ({i},{task_mean[t]:.2f})")
print("};")

print()
print("% TikZ coordinates for K tasks:")
print("\\addplot coordinates {")
for i, t in enumerate(tasks):
    if t in K_TASKS:
        print(f"  ({i},{task_mean[t]:.2f})")
print("};")

print()
print("% TikZ coordinates for T10:")
print("\\addplot coordinates {")
for i, t in enumerate(tasks):
    if t == "T10":
        print(f"  ({i},{task_mean[t]:.2f})")
print("};")

print()
print("% xtick labels:")
labels = ", ".join(t for t in tasks)
print(f"% {labels}")
print()
print(f"% Total tasks: {len(tasks)}")
print()

# Print summary table
print("% idx | task | gt_files | mean_score | category")
for i, t in enumerate(tasks):
    cat = "K" if t in K_TASKS else ("T10" if t == "T10" else "")
    print(f"% {i:3d} | {t:4s} | {gt_files[t]:5d} | {task_mean[t]:5.2f} | {cat}")
