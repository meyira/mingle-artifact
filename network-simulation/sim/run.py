import argparse, os
from .config import SimConfig
from .sim_core import Sim

def main():
    ap = argparse.ArgumentParser()
    # scale/time
    ap.add_argument("--users", type=int, default=100000)
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--dt_min", type=int, default=5)
    # graph
    ap.add_argument("--avg_contacts", type=int, default=25)
    ap.add_argument("--groups", type=int, default=20000)
    ap.add_argument("--avg_group_size", type=int, default=12)
    # targeted-cohort mixing (homophily across the victim cut)
    ap.add_argument("--p_contact_cross", type=float, default=1.0)
    ap.add_argument("--p_group_cross", type=float, default=1.0)
    # behavior
    ap.add_argument("--active_hour_mu", type=float, default=20.5)
    ap.add_argument("--active_hour_sigma", type=float, default=3.0)
    ap.add_argument("--active_span_hours", type=float, default=14.0)
    ap.add_argument("--msg_rate_1to1", type=float, default=0.10)
    ap.add_argument("--msg_rate_group", type=float, default=0.06)
    # gossip
    ap.add_argument("--mode", choices=["sth_only","sth_proof"], default="sth_proof")
    ap.add_argument("--p_gossip", type=float, default=0.6)
    ap.add_argument("--sth_bytes", type=int, default=128)
    ap.add_argument("--proof_bytes", type=int, default=768)
    ap.add_argument("--adoption", type=float, default=0.8)
    # server behavior
    ap.add_argument("--server_mode", type=str, default="permanent_fork",
                    choices=["honest","permanent_fork","transient_fork","rolling","freeze","regional"])
    ap.add_argument("--fork_hour", type=float, default=12.0)
    ap.add_argument("--fork_frac", type=float, default=0.5)
    ap.add_argument("--fork_duration", type=float, default=None)
    ap.add_argument("--sth_period_hours", type=float, default=1.0)
    ap.add_argument("--p_equiv", type=float, default=0.0)
    ap.add_argument("--sticky_victims", action="store_true", default=True)
    ap.add_argument("--no_sticky_victims", dest="sticky_victims", action="store_false")
    ap.add_argument("--proof_withhold_rate", type=float, default=0.0)
    ap.add_argument("--proof_timeout_rate", type=float, default=0.0)
    ap.add_argument("--invalid_proof_rate", type=float, default=0.0)
    ap.add_argument("--p_drop_crosscut", type=float, default=0.0)
    ap.add_argument("--witness_required", action="store_true", default=False)
    # misc
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outdir", type=str, default="out")
    args = ap.parse_args()

    cfg = SimConfig(
        users=args.users, hours=args.hours, dt_min=args.dt_min,
        avg_contacts=args.avg_contacts, groups=args.groups, avg_group_size=args.avg_group_size,
        p_contact_cross=args.p_contact_cross, p_group_cross=args.p_group_cross,
        active_hour_mu=args.active_hour_mu, active_hour_sigma=args.active_hour_sigma, active_span_hours=args.active_span_hours,
        msg_rate_1to1=args.msg_rate_1to1, msg_rate_group=args.msg_rate_group,
        mode=args.mode, p_gossip=args.p_gossip, sth_bytes=args.sth_bytes, proof_bytes=args.proof_bytes,
        adoption=args.adoption,
        server_mode=args.server_mode, fork_hour=args.fork_hour, fork_frac=args.fork_frac,
        fork_duration=args.fork_duration, sth_period_hours=args.sth_period_hours,
        p_equiv=args.p_equiv, sticky_victims=args.sticky_victims,
        proof_withhold_rate=args.proof_withhold_rate, proof_timeout_rate=args.proof_timeout_rate,
        invalid_proof_rate=args.invalid_proof_rate,
        p_drop_crosscut=args.p_drop_crosscut, witness_required=args.witness_required,
        seed=args.seed, outdir=args.outdir
    )

    os.makedirs(cfg.outdir, exist_ok=True)
    Sim(cfg).run()
    print(f"Done. See {cfg.outdir}/summary.json and {cfg.outdir}/timeline.csv.")

if __name__ == "__main__":
    main()
