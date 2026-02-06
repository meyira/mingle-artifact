import csv, json, os

class Metrics:
    def __init__(self, outdir="out"):
        self.outdir = outdir
        os.makedirs(outdir, exist_ok=True)

        # timeline row:
        # (tick, aware_users, evidence_users, bytes, proofs_ok, proofs_incons, proofs_withhold, proofs_timeout, xcut, xcut_dropped)
        self.timeline = []
        self.events = []  # (tick, user, "aware"|"evidence")

        self.first_aware_tick = None
        self.first_evidence_tick = None

        self.total_gossip_bytes = 0
        self.total_msgs = 0

        # Totals
        self.proof_ok = 0
        self.proof_inconsistent = 0
        self.proof_withhold = 0
        self.proof_timeout = 0
        self.crosscut_deliveries = 0
        self.crosscut_dropped = 0

        # last snapshot
        self._last_aware = 0
        self._last_evidence = 0

    def log_timeline(self, tick, aware_users, evidence_users, bytes_this_tick,
                     pr_ok, pr_inc, pr_withhold, pr_timeout,
                     xcut, xcut_drop):
        self.timeline.append((tick, aware_users, evidence_users, bytes_this_tick,
                              pr_ok, pr_inc, pr_withhold, pr_timeout,
                              xcut, xcut_drop))
        self._last_aware = int(aware_users)
        self._last_evidence = int(evidence_users)

    def add_event(self, tick, user, kind):
        kind = str(kind)
        self.events.append((int(tick), int(user), kind))
        if kind == "aware" and self.first_aware_tick is None:
            self.first_aware_tick = int(tick)
        if kind in ("evidence", "detect") and self.first_evidence_tick is None:
            # Backwards-compat: treat "detect" as evidence.
            self.first_evidence_tick = int(tick)

    def add_bytes(self, b):
        self.total_gossip_bytes += int(b)

    def add_msgs(self, n=1):
        self.total_msgs += int(n)

    def write(self, summary_extra=None):
        # timeline
        with open(os.path.join(self.outdir, "timeline.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            # Keep 'detectors' for backwards compatibility with older notebooks,
            # but also include 'evidence_users' as the preferred name.
            w.writerow([
                "tick",
                "aware_users",
                "detectors",        # alias for evidence_users
                "evidence_users",
                "gossip_bytes_this_tick",
                "proofs_ok","proofs_inconsistent","proofs_withhold","proofs_timeout",
                "crosscut_deliveries","crosscut_dropped"
            ])
            for (tick, aware_u, evid_u, bytes_tick, pr_ok, pr_inc, pr_w, pr_t, xcut, xdrop) in self.timeline:
                w.writerow([
                    tick,
                    aware_u,
                    evid_u,
                    evid_u,
                    bytes_tick,
                    pr_ok, pr_inc, pr_w, pr_t,
                    xcut, xdrop
                ])

        # events
        with open(os.path.join(self.outdir, "events.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["tick","user","event"])
            for e in self.events:
                w.writerow(list(e))

        summary = {
            "first_awareness_tick": self.first_aware_tick,
            "first_evidence_tick": self.first_evidence_tick,
            "aware_end": self._last_aware,
            "evidence_end": self._last_evidence,

            "total_gossip_bytes": self.total_gossip_bytes,
            "total_messages": self.total_msgs,

            "proof_ok": self.proof_ok,
            "proof_inconsistent": self.proof_inconsistent,
            "proof_withhold": self.proof_withhold,
            "proof_timeout": self.proof_timeout,

            "crosscut_deliveries": self.crosscut_deliveries,
            "crosscut_dropped": self.crosscut_dropped,
        }
        if summary_extra:
            summary.update(summary_extra)

        with open(os.path.join(self.outdir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
