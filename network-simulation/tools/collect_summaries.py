import argparse, csv, json, os
from glob import glob

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Root folder containing run subfolders")
    ap.add_argument("--out", required=True, help="Output CSV path")
    args = ap.parse_args()

    summaries = []
    for path in glob(os.path.join(args.root, "*", "summary.json")):
        with open(path, "r", encoding="utf-8") as f:
            s = json.load(f)
        s["_run_dir"] = os.path.dirname(path)
        s["_run_name"] = os.path.basename(os.path.dirname(path))
        summaries.append(s)

    if not summaries:
        raise SystemExit(f"No summary.json found under {args.root}")

    # Union of keys across all summaries (stable order: some common first, then rest sorted)
    preferred = [
        "_run_name","users","hours","dt_min",
        "server_mode","fork_hour","fork_duration","fork_frac","p_equiv","p_drop_crosscut","witness_required",
        "mode","p_gossip","adoption","avg_contacts","groups","avg_group_size",
        "p_self_audit","p_anon_check",
        "first_detection_tick","total_gossip_bytes","total_messages",
        "proof_ok","proof_inconsistent","proof_withhold","proof_timeout",
        "crosscut_deliveries","crosscut_dropped",
        "self_audits","self_audit_fail","anon_checks","anon_mismatch",
    ]
    all_keys = set().union(*[set(s.keys()) for s in summaries])
    rest = sorted([k for k in all_keys if k not in preferred])
    fieldnames = [k for k in preferred if k in all_keys] + rest

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for s in sorted(summaries, key=lambda x: x.get("_run_name","")):
            w.writerow({k: s.get(k, "") for k in fieldnames})

    print(f"Wrote {len(summaries)} rows to {args.out}")

if __name__ == "__main__":
    main()
