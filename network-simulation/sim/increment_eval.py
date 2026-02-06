#!/usr/bin/env python3

import os, sys, re, json, time, subprocess
from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# --------------------------
# Repo + entrypoint discovery
# --------------------------

REPO_ROOT = Path.cwd()
if not (REPO_ROOT / "sim").exists():
    # try parents
    for p in [REPO_ROOT] + list(REPO_ROOT.parents):
        if (p / "sim").exists():
            REPO_ROOT = p
            break

if not (REPO_ROOT / "sim").exists():
    raise RuntimeError("Could not find repo root containing `sim/`. Run from repo root.")

# prefer .venv python
venv_py_win = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
venv_py_unix = REPO_ROOT / ".venv" / "bin" / "python"
if venv_py_win.exists():
    PYTHON = str(venv_py_win)
elif venv_py_unix.exists():
    PYTHON = str(venv_py_unix)
else:
    PYTHON = sys.executable

def detect_entrypoint():
    p = subprocess.run([PYTHON, "-m", "sim.run", "--help"], cwd=REPO_ROOT,
                       capture_output=True, text=True)
    if p.returncode == 0:
        return ["-m", "sim.run"]
    run_py = REPO_ROOT / "sim" / "run.py"
    if run_py.exists():
        p2 = subprocess.run([PYTHON, str(run_py), "--help"], cwd=REPO_ROOT,
                            capture_output=True, text=True)
        if p2.returncode == 0:
            return [str(run_py)]
    raise RuntimeError("Could not detect simulator entrypoint (sim.run or sim/run.py).")

ENTRY = detect_entrypoint()

# get supported flags
help_p = subprocess.run([PYTHON] + ENTRY + ["--help"], cwd=REPO_ROOT, capture_output=True, text=True)
HELP_TEXT = (help_p.stdout or "") + "\n" + (help_p.stderr or "")
SUPPORTED_FLAGS = set(re.findall(r"(--[a-zA-Z0-9_]+)", HELP_TEXT))

print("Repo root:", REPO_ROOT)
print("Python:", PYTHON)
print("Entry:", ENTRY)
print("Supported flags:", len(SUPPORTED_FLAGS))

# --------------------------
# Helpers: run + load + metrics
# --------------------------

def params_to_args(params: dict):
    args = []
    for k, v in params.items():
        flag = f"--{k}"
        if flag not in SUPPORTED_FLAGS:
            continue
        if v is None:
            continue
        if isinstance(v, bool):
            if v:
                args.append(flag)
        else:
            args.extend([flag, str(v)])
    return args

def run_sim(params: dict, outdir: Path):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    p = dict(params)
    p["outdir"] = str(outdir)

    cmd = [PYTHON] + ENTRY + params_to_args(p)

    t0 = time.time()
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    wall_s = time.time() - t0

    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise RuntimeError(f"Simulation failed rc={proc.returncode}")
    return wall_s

def load_run(outdir: Path):
    outdir = Path(outdir)
    summary_path  = outdir / "summary.json"
    timeline_path = outdir / "timeline.csv"
    events_path   = outdir / "events.csv"

    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    timeline = pd.read_csv(timeline_path) if timeline_path.exists() else pd.DataFrame()
    events = pd.read_csv(events_path) if events_path.exists() else pd.DataFrame()
    return summary, timeline, events

def time_to_fraction(timeline: pd.DataFrame, users: int, dt_min: float, frac: float):
    if timeline.empty or users <= 0:
        return np.nan
    if "detectors" not in timeline.columns or "tick" not in timeline.columns:
        return np.nan
    target = frac * users
    det = timeline["detectors"].to_numpy()
    ticks = timeline["tick"].to_numpy()
    idx = np.where(det >= target)[0]
    if len(idx) == 0:
        return np.nan
    return float(ticks[idx[0]]) * dt_min

def derived_metrics(summary: dict, timeline: pd.DataFrame, fallback: dict, detection_policy="strict"):
    users = int(summary.get("users", fallback.get("users", 0)))
    dt_min = float(summary.get("dt_min", fallback.get("dt_min", 5)))
    fork_hour = float(summary.get("fork_hour", fallback.get("fork_hour", 0)))

    pr_ok   = int(summary.get("proof_ok", 0))
    pr_inc  = int(summary.get("proof_inconsistent", 0))
    pr_with = int(summary.get("proof_withhold", 0))
    pr_to   = int(summary.get("proof_timeout", 0))

    if detection_policy == "soft":
        detected = (pr_inc + pr_with + pr_to) > 0
    else:
        detected = pr_inc > 0

    # first detection latency since fork
    first_tick = summary.get("first_detection_tick", None)
    latency_min = np.nan
    if detected and first_tick not in (None, ""):
        try:
            t_detect_min = float(first_tick) * dt_min
            latency_min = max(0.0, t_detect_min - fork_hour * 60.0)
        except Exception:
            pass

    # coverage at end
    det_frac_end = np.nan
    if not timeline.empty and "detectors" in timeline.columns and users > 0:
        det_frac_end = float(timeline["detectors"].iloc[-1]) / users

    # time-to-X% detection
    t10 = time_to_fraction(timeline, users, dt_min, 0.10)
    t50 = time_to_fraction(timeline, users, dt_min, 0.50)

    # overhead (paper-grade)
    total_gossip_bytes = float(summary.get("total_gossip_bytes", np.nan))
    total_sends = float(summary.get("total_sends", np.nan))
    total_deliv = float(summary.get("total_deliveries", summary.get("total_messages", np.nan)))

    bps = (total_gossip_bytes / total_sends) if np.isfinite(total_gossip_bytes) and total_sends > 0 else np.nan
    bpd = (total_gossip_bytes / total_deliv) if np.isfinite(total_gossip_bytes) and total_deliv > 0 else np.nan

    out = dict(
        server_mode=summary.get("server_mode", fallback.get("server_mode")),
        mode=summary.get("mode", fallback.get("mode")),
        users=users,
        hours=float(summary.get("hours", fallback.get("hours", np.nan))),
        p_gossip=float(summary.get("p_gossip", fallback.get("p_gossip", np.nan))),
        adoption=float(summary.get("adoption", fallback.get("adoption", np.nan))),
        fork_frac=float(summary.get("fork_frac", fallback.get("fork_frac", np.nan))),
        fork_hour=float(summary.get("fork_hour", fallback.get("fork_hour", np.nan))),
        p_drop_crosscut=float(summary.get("p_drop_crosscut", fallback.get("p_drop_crosscut", np.nan))),
        proof_withhold_rate=float(summary.get("proof_withhold_rate", fallback.get("proof_withhold_rate", np.nan))),
        proof_timeout_rate=float(summary.get("proof_timeout_rate", fallback.get("proof_timeout_rate", np.nan))),
        invalid_proof_rate=float(summary.get("invalid_proof_rate", fallback.get("invalid_proof_rate", np.nan))),
        crosscuts=float(summary.get("crosscut_deliveries", 0)),
        detected=bool(detected),
        latency_min=latency_min,
        det_frac_end=det_frac_end,
        t10_min=t10,
        t50_min=t50,
        bytes_per_send=bps,
        bytes_per_delivery=bpd,
        proof_inconsistent=pr_inc,
        proof_total=(pr_ok + pr_inc + pr_with + pr_to),
        seed=int(summary.get("seed", fallback.get("seed", -1))),
    )

    # optional knobs (if supported)
    for k in ["p_contact_cross","p_group_cross","groups","avg_group_size","msg_rate_group","msg_rate_1to1","sticky_victims","no_sticky_victims"]:
        if k in summary or k in fallback:
            out[k] = summary.get(k, fallback.get(k))
    return out

def safe_name(v):
    if isinstance(v, float):
        return f"{v:g}".replace(".", "p")
    return str(v).replace("/", "_")

def make_outdir_name(cfg, seed):
    parts = [
        cfg.get("server_mode","m"),
        cfg.get("mode","x"),
        f"n{cfg.get('users',0)}",
        f"pg{safe_name(cfg.get('p_gossip',0))}",
        f"a{safe_name(cfg.get('adoption',0))}",
        f"ff{safe_name(cfg.get('fork_frac',0))}",
        f"s{seed}",
    ]
    if "p_drop_crosscut" in cfg:
        parts.append(f"drop{safe_name(cfg.get('p_drop_crosscut',0))}")
    if "p_contact_cross" in cfg:
        parts.append(f"pc{safe_name(cfg.get('p_contact_cross',1))}")
    if "p_group_cross" in cfg:
        parts.append(f"pgc{safe_name(cfg.get('p_group_cross',1))}")
    return "_".join(parts)

def run_grid(base: dict, sweep: dict, replicates: int, seed_base: int, outroot: Path, detection_policy="strict"):
    outroot = Path(outroot)
    outroot.mkdir(parents=True, exist_ok=True)
    rows = []
    keys = list(sweep.keys())
    total = int(np.prod([len(sweep[k]) for k in keys]) * replicates)
    done = 0

    for vals in product(*[sweep[k] for k in keys]):
        cfg = dict(base)
        cfg.update({k: v for k, v in zip(keys, vals)})

        for r in range(replicates):
            seed = seed_base + r
            cfg_run = dict(cfg)
            cfg_run["seed"] = seed
            outdir = outroot / make_outdir_name(cfg_run, seed)

            wall_s = run_sim(cfg_run, outdir)
            summary, timeline, _ = load_run(outdir)
            dm = derived_metrics(summary, timeline, fallback=cfg_run, detection_policy=detection_policy)
            dm["run_dir"] = str(outdir)
            dm["wall_s"] = wall_s
            rows.append(dm)

            done += 1
            if done % 10 == 0:
                print(f"{done}/{total} done")
    return pd.DataFrame(rows)

def aggregate(df_raw: pd.DataFrame, group_cols):
    return df_raw.groupby(group_cols, dropna=False).agg(
        reps=("run_dir","count"),
        wall_s_med=("wall_s","median"),
        detected_rate=("detected","mean"),
        det_frac_end_mean=("det_frac_end","mean"),
        t10_med=("t10_min","median"),
        t50_med=("t50_min","median"),
        lat_med=("latency_min","median"),
        bpd_mean=("bytes_per_delivery","mean"),
        bps_mean=("bytes_per_send","mean"),
        crosscuts_mean=("crosscuts","mean"),
    ).reset_index()

def save_plot(path_no_ext: Path):
    path_no_ext.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path_no_ext.with_suffix(".png"), dpi=300)
    plt.savefig(path_no_ext.with_suffix(".pdf"))
    plt.close()

# --------------------------
# Baselines (small + laptop)
# --------------------------

BASE_SMALL = dict(
    users=500, hours=2, dt_min=5,
    avg_contacts=25, groups=800, avg_group_size=10,
    active_hour_mu=14, active_hour_sigma=4, active_span_hours=10.0,
    msg_rate_1to1=0.08, msg_rate_group=0.04,
    mode="sth_proof", p_gossip=0.2, adoption=0.5,
    server_mode="permanent_fork", fork_hour=1.0, fork_frac=0.1, fork_duration=1.0,
    sth_period_hours=1.0, p_equiv=0.0,
    proof_withhold_rate=0.0, proof_timeout_rate=0.0, invalid_proof_rate=0.0,
    p_drop_crosscut=0.0, witness_required=False,
    seed=1,
)

BASE_LAPTOP = dict(BASE_SMALL)
BASE_LAPTOP.update(
    users=2000, hours=3, fork_hour=1.5, fork_frac=0.05,
    groups=4000, avg_group_size=12,
    msg_rate_1to1=0.06, msg_rate_group=0.03,
    p_gossip=0.05, adoption=0.3,
    seed=42,
)

OUT = REPO_ROOT / "out_incremental_py"
OUT.mkdir(parents=True, exist_ok=True)

# --------------------------
# Experiment 0: Performance ramp
# --------------------------

print("\n=== Experiment 0: performance ramp ===")
ramp_users = [500, 1000, 2000, 5000, 8000, 12000]
ramp_rows = []
for n in ramp_users:
    cfg = dict(BASE_LAPTOP)
    cfg.update(users=n, hours=1.0, fork_hour=0.5, server_mode="honest", p_gossip=0.0, adoption=0.0)
    cfg["groups"] = int(min(4*n, 20000))  # cap expensive groups
    cfg["avg_group_size"] = 10
    cfg["msg_rate_group"] = 0.02
    cfg["msg_rate_1to1"] = 0.05
    outdir = OUT / "ramp" / f"n{n}"
    wall_s = run_sim(cfg, outdir)
    summary, _, _ = load_run(outdir)
    ramp_rows.append(dict(
        users=n, wall_s=wall_s,
        total_deliveries=summary.get("total_deliveries", summary.get("total_messages", np.nan)),
        total_sends=summary.get("total_sends", np.nan),
        groups=cfg["groups"],
    ))
    print(f"users={n} wall_s={wall_s:.2f}")

df_ramp = pd.DataFrame(ramp_rows)
df_ramp.to_csv(OUT / "ramp.csv", index=False)

plt.figure()
plt.plot(df_ramp["users"], df_ramp["wall_s"], marker="o")
plt.xlabel("users")
plt.ylabel("wall-clock seconds (1h sim)")
plt.title("Performance ramp (this machine)")
save_plot(OUT / "fig_ramp")

# --------------------------
# Experiment 1: Correctness sanity
# --------------------------

print("\n=== Experiment 1: correctness sanity ===")

def one_run(name: str, cfg: dict):
    outdir = OUT / "sanity" / name
    wall_s = run_sim(cfg, outdir)
    summary, timeline, _ = load_run(outdir)
    dm = derived_metrics(summary, timeline, fallback=cfg, detection_policy="strict")
    dm["wall_s"] = wall_s
    dm["name"] = name
    return dm

san = []
cfg = dict(BASE_SMALL); cfg.update(server_mode="honest", p_gossip=0.2, adoption=0.5)
san.append(one_run("honest", cfg))
cfg = dict(BASE_SMALL); cfg.update(server_mode="permanent_fork", p_gossip=0.0, adoption=0.0)
san.append(one_run("fork_no_gossip", cfg))
cfg = dict(BASE_SMALL); cfg.update(server_mode="permanent_fork", p_gossip=0.2, adoption=0.5)
san.append(one_run("fork_with_gossip", cfg))

df_san = pd.DataFrame(san)
df_san.to_csv(OUT / "sanity.csv", index=False)
print(df_san[["name","server_mode","p_gossip","adoption","detected","det_frac_end","t10_min","t50_min","bytes_per_delivery","crosscuts","wall_s"]])

# --------------------------
# Experiment 2: Sweep p_gossip
# --------------------------

print("\n=== Experiment 2: sweep p_gossip ===")
OUT_PG = OUT / "sweep_pgossip"
base = dict(BASE_LAPTOP)
base.update(server_mode="permanent_fork", mode="sth_proof", adoption=0.3)
sweep = dict(p_gossip=[0.0, 0.01, 0.05, 0.1, 0.2, 0.4], users=[2000])

df_raw_pg = run_grid(base, sweep, replicates=5, seed_base=1000, outroot=OUT_PG, detection_policy="strict")
df_raw_pg.to_csv(OUT_PG / "raw.csv", index=False)

group_cols = ["users","adoption","p_gossip","server_mode","mode"]
df_agg_pg = aggregate(df_raw_pg, group_cols).sort_values("p_gossip")
df_agg_pg.to_csv(OUT_PG / "agg.csv", index=False)

plt.figure()
plt.plot(df_agg_pg["p_gossip"], df_agg_pg["det_frac_end_mean"], marker="o")
plt.xlabel("p_gossip"); plt.ylabel("mean coverage (end)")
plt.title("Coverage vs p_gossip")
save_plot(OUT_PG / "fig_cov_vs_pgossip")

plt.figure()
plt.plot(df_agg_pg["p_gossip"], df_agg_pg["t10_med"], marker="o", label="t10")
plt.plot(df_agg_pg["p_gossip"], df_agg_pg["t50_med"], marker="o", label="t50")
plt.xlabel("p_gossip"); plt.ylabel("minutes")
plt.title("Time-to-X% vs p_gossip")
plt.legend()
save_plot(OUT_PG / "fig_tX_vs_pgossip")

plt.figure()
plt.plot(df_agg_pg["p_gossip"], df_agg_pg["bpd_mean"], marker="o")
plt.xlabel("p_gossip"); plt.ylabel("bytes per delivery")
plt.title("Overhead vs p_gossip")
save_plot(OUT_PG / "fig_overhead_vs_pgossip")

# --------------------------
# Experiment 3: Sweep adoption
# --------------------------

print("\n=== Experiment 3: sweep adoption ===")
OUT_AD = OUT / "sweep_adoption"
base = dict(BASE_LAPTOP)
base.update(server_mode="permanent_fork", mode="sth_proof", p_gossip=0.05)
sweep = dict(adoption=[0.0, 0.1, 0.3, 0.6, 1.0], users=[2000])

df_raw_ad = run_grid(base, sweep, replicates=5, seed_base=2000, outroot=OUT_AD, detection_policy="strict")
df_raw_ad.to_csv(OUT_AD / "raw.csv", index=False)

group_cols = ["users","adoption","p_gossip","server_mode","mode"]
df_agg_ad = aggregate(df_raw_ad, group_cols).sort_values("adoption")
df_agg_ad.to_csv(OUT_AD / "agg.csv", index=False)

plt.figure()
plt.plot(df_agg_ad["adoption"], df_agg_ad["det_frac_end_mean"], marker="o")
plt.xlabel("adoption"); plt.ylabel("mean coverage (end)")
plt.title("Coverage vs adoption")
save_plot(OUT_AD / "fig_cov_vs_adoption")

plt.figure()
plt.plot(df_agg_ad["adoption"], df_agg_ad["t10_med"], marker="o", label="t10")
plt.plot(df_agg_ad["adoption"], df_agg_ad["t50_med"], marker="o", label="t50")
plt.xlabel("adoption"); plt.ylabel("minutes")
plt.title("Time-to-X% vs adoption")
plt.legend()
save_plot(OUT_AD / "fig_tX_vs_adoption")

# --------------------------
# Experiment 4: Targeted + mixing knobs (if supported)
# --------------------------

print("\n=== Experiment 4: targeted fork + (optional) reduced mixing ===")
OUT_TARG = OUT / "targeted_mixing"
base = dict(BASE_LAPTOP)
base.update(server_mode="permanent_fork", mode="sth_proof", sticky_victims=True, fork_frac=0.05)
# these will be ignored if unsupported by your CLI
base.update(p_contact_cross=0.02, p_group_cross=0.02)

sweep = dict(p_gossip=[0.01, 0.05, 0.2], adoption=[0.1, 0.3, 0.6, 1.0], users=[2000])
df_raw_targ = run_grid(base, sweep, replicates=5, seed_base=3000, outroot=OUT_TARG, detection_policy="strict")
df_raw_targ.to_csv(OUT_TARG / "raw.csv", index=False)

group_cols = ["users","p_gossip","adoption","fork_frac","server_mode","mode"]
if "p_contact_cross" in df_raw_targ.columns:
    group_cols += ["p_contact_cross","p_group_cross"]
df_agg_targ = aggregate(df_raw_targ, group_cols).sort_values(["adoption","p_gossip"])
df_agg_targ.to_csv(OUT_TARG / "agg.csv", index=False)

# heatmap helpers
def heatmap(df_agg, value_col, title, xcol="p_gossip", ycol="adoption", outpath=None):
    hm = df_agg.copy()
    xs = sorted(hm[xcol].dropna().unique())
    ys = sorted(hm[ycol].dropna().unique())
    X = {x:i for i,x in enumerate(xs)}
    Y = {y:i for i,y in enumerate(ys)}
    Z = np.full((len(ys), len(xs)), np.nan)
    for _, r in hm.iterrows():
        Z[Y[r[ycol]], X[r[xcol]]] = r[value_col]
    plt.figure()
    plt.imshow(Z, aspect="auto", origin="lower")
    plt.xticks(range(len(xs)), [f"{x:g}" for x in xs], rotation=45)
    plt.yticks(range(len(ys)), [f"{y:g}" for y in ys])
    plt.xlabel(xcol); plt.ylabel(ycol); plt.title(title)
    plt.colorbar()
    if outpath:
        save_plot(outpath)
    else:
        plt.show()

heatmap(df_agg_targ, "det_frac_end_mean", "Coverage end — targeted", outpath=OUT_TARG/"fig_heat_cov")
heatmap(df_agg_targ, "t10_med", "t10 (min) — targeted", outpath=OUT_TARG/"fig_heat_t10")
heatmap(df_agg_targ, "bpd_mean", "Bytes/delivery — targeted", outpath=OUT_TARG/"fig_heat_overhead")

# --------------------------
# Experiment 5: Suppression (drop crosscuts)
# --------------------------

print("\n=== Experiment 5: suppression (p_drop_crosscut) ===")
OUT_SUP = OUT / "suppression"
base = dict(BASE_LAPTOP)
base.update(server_mode="permanent_fork", mode="sth_proof", p_gossip=0.05, adoption=0.3)
sweep = dict(p_drop_crosscut=[0.0, 0.3, 0.6, 0.9], users=[2000])

df_raw_sup = run_grid(base, sweep, replicates=5, seed_base=4000, outroot=OUT_SUP, detection_policy="strict")
df_raw_sup.to_csv(OUT_SUP / "raw.csv", index=False)

group_cols = ["users","p_drop_crosscut","p_gossip","adoption","server_mode","mode"]
df_agg_sup = aggregate(df_raw_sup, group_cols).sort_values("p_drop_crosscut")
df_agg_sup.to_csv(OUT_SUP / "agg.csv", index=False)

plt.figure()
plt.plot(df_agg_sup["p_drop_crosscut"], df_agg_sup["det_frac_end_mean"], marker="o")
plt.xlabel("p_drop_crosscut"); plt.ylabel("mean coverage (end)")
plt.title("Suppression reduces coverage")
save_plot(OUT_SUP / "fig_cov_vs_drop")

plt.figure()
plt.plot(df_agg_sup["p_drop_crosscut"], df_agg_sup["t10_med"], marker="o", label="t10")
plt.plot(df_agg_sup["p_drop_crosscut"], df_agg_sup["t50_med"], marker="o", label="t50")
plt.xlabel("p_drop_crosscut"); plt.ylabel("minutes")
plt.title("Suppression increases time-to-X%")
plt.legend()
save_plot(OUT_SUP / "fig_tX_vs_drop")

# --------------------------
# Experiment 6: Proof adversary (strict vs soft)
# --------------------------

print("\n=== Experiment 6: proof adversary (strict vs soft) ===")
OUT_PROOF = OUT / "proof_adversary"
base = dict(BASE_LAPTOP)
base.update(server_mode="permanent_fork", mode="sth_proof", p_gossip=0.05, adoption=0.3)
sweep = dict(proof_withhold_rate=[0.0, 0.3, 0.6], proof_timeout_rate=[0.0, 0.3], users=[2000])

df_raw_strict = run_grid(base, sweep, replicates=3, seed_base=5000, outroot=OUT_PROOF/"strict", detection_policy="strict")
df_raw_soft   = run_grid(base, sweep, replicates=3, seed_base=6000, outroot=OUT_PROOF/"soft", detection_policy="soft")
df_raw_strict.to_csv(OUT_PROOF/"strict_raw.csv", index=False)
df_raw_soft.to_csv(OUT_PROOF/"soft_raw.csv", index=False)

group_cols = ["users","proof_withhold_rate","proof_timeout_rate","p_gossip","adoption","server_mode","mode"]
agg_strict = aggregate(df_raw_strict, group_cols).rename(columns={
    "det_frac_end_mean":"det_end_strict","t10_med":"t10_strict","t50_med":"t50_strict"
})
agg_soft = aggregate(df_raw_soft, group_cols).rename(columns={
    "det_frac_end_mean":"det_end_soft","t10_med":"t10_soft","t50_med":"t50_soft"
})

merged = pd.merge(agg_strict, agg_soft, on=group_cols, how="inner")
merged.to_csv(OUT_PROOF/"merged.csv", index=False)
print(merged[["proof_withhold_rate","proof_timeout_rate","det_end_strict","det_end_soft","t10_strict","t10_soft"]]
      .sort_values(["proof_withhold_rate","proof_timeout_rate"]))

print("\nDone. Outputs in:", OUT)

# End of file
