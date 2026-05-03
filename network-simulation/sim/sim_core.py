import numpy as np

from .config import SimConfig
from .graph import gen_contacts, gen_groups
from .metrics import Metrics
from .server import Server, ServerBehavior
from .server import ProofResult, BRANCH_A, BRANCH_B
from .client_logic import recv_gossip


class Sim:
    def __init__(self, cfg: SimConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)

        # Separate RNG stream for censorship so changing p_drop_crosscut
        # does not perturb traffic.
        self.drop_rng = np.random.default_rng(cfg.seed + 123)

        self.n = cfg.users

        # Activity windows
        self.active_start, self.active_end = self._sample_active_window(
            self.n,
            cfg.active_hour_mu,
            cfg.active_hour_sigma,
            cfg.active_span_hours,
        )
        self.adopts = self.rng.random(self.n) < cfg.adoption

        # Social graph
        self.contacts = gen_contacts(self.n, cfg.avg_contacts, self.rng)
        if cfg.groups > 0:
            self.groups, self.user_groups = gen_groups(
                self.n,
                cfg.groups,
                cfg.avg_group_size,
                self.rng,
            )
        else:
            self.groups = []
            self.user_groups = [[] for _ in range(self.n)]

        # KT client state
        self.version = np.zeros(self.n, dtype=np.int32)
        self.branch = np.zeros(self.n, dtype=np.int8)
        self.aware = np.zeros(self.n, dtype=bool)
        self.detector = np.zeros(self.n, dtype=bool)
        self.suspicion = np.zeros(self.n, dtype=np.int32)

        # Fork cohort mask
        self.fork_mask = self.rng.random(self.n) < cfg.fork_frac

        # Server behavior
        beh = ServerBehavior(
            mode=cfg.server_mode,
            fork_hour=cfg.fork_hour,
            fork_duration=cfg.fork_duration,
            p_equiv=cfg.p_equiv,
            sticky_victims=cfg.sticky_victims,
            fork_mask=self.fork_mask,
            sth_period_hours=cfg.sth_period_hours,
            proof_withhold_rate=cfg.proof_withhold_rate,
            proof_timeout_rate=cfg.proof_timeout_rate,
            invalid_proof_rate=cfg.invalid_proof_rate,
            witness_required=cfg.witness_required,
            rng_seed=cfg.seed + 7,
        )
        self.server = Server(beh)

        # Metrics
        self.metrics = Metrics(outdir=cfg.outdir)
        self.per_msg_bytes = cfg.sth_bytes + (
            cfg.proof_bytes if cfg.mode == "sth_proof" else 0
        )

        self._now_hour = 0.0

    # === Helpers ===

    def _sample_active_window(self, n, mu, sigma, span_mean):
        span = np.maximum(8.0, self.rng.normal(loc=span_mean, scale=1.5, size=n))
        start = self.rng.normal(loc=mu - span / 2, scale=sigma, size=n)
        start = np.mod(start, 24.0)
        end = (start + span) % 24.0
        return start, end

    @staticmethod
    def _in_window(t_hour, start, end):
        if start <= end:
            return start <= t_hour < end
        return not (end <= t_hour < start)

    def _is_active(self, u, hour):
        return self._in_window(hour, self.active_start[u], self.active_end[u])

    def _maybe_send(self, u):
        deliveries = []

        # 1:1
        if self.rng.random() < self.cfg.msg_rate_1to1:
            dsts = self.contacts[u]
            if len(dsts) > 0:
                v = int(self.rng.choice(dsts))
                deliveries.append(np.array([v], dtype=np.int32))

        # group
        if (
            self.cfg.groups > 0
            and self.rng.random() < self.cfg.msg_rate_group
            and len(self.user_groups[u]) > 0
        ):
            gid = int(self.rng.choice(self.user_groups[u]))
            deliveries.append(self.groups[gid])

        return deliveries

    def _refresh_to_current(self, u):
        period = max(self.cfg.sth_period_hours, 1e-9)
        cur_epoch = int(self._now_hour / period)
        if self.version[u] == 0 or self.version[u] < cur_epoch:
            br, ver = self.server.current_sth(u, self._now_hour)
            self.branch[u] = br
            self.version[u] = ver

    def _attach_sth(self, u):
        self._refresh_to_current(u)
        return int(self.branch[u]), int(self.version[u])

    # === Main loop ===

    def run(self):
        ticks = int(self.cfg.hours * 60 / self.cfg.dt_min)

        for t in range(ticks):
            self._now_hour = (t * self.cfg.dt_min) / 60.0
            active = [u for u in range(self.n) if self._is_active(u, self._now_hour)]

            bytes_tick = 0

            # per-tick stats
            pr_ok = 0
            pr_inc = 0
            pr_withhold = 0
            pr_timeout = 0
            xcut = 0
            xcut_drop = 0

            for u in active:
                deliveries = self._maybe_send(u)

                for dst_arr in deliveries:
                    # Decide once per logical outgoing message whether it carries gossip.
                    send_gossip = bool(
                        self.adopts[u] and (self.rng.random() < self.cfg.p_gossip)
                    )

                    br_send = None
                    ver_send = None
                    if send_gossip:
                        br_send, ver_send = self._attach_sth(u)

                    for v in dst_arr:
                        v = int(v)

                        # Count every recipient-level application message.
                        self.metrics.add_msgs(1)

                        # No gossip attached to this application message.
                        if not send_gossip:
                            continue

                        # Cross-cut suppression: drop A<->B deliveries after fork.
                        # Compare the sender's attached branch with the receiver's
                        # current server view.
                        br_pred_v, _ = self.server.current_sth(v, self._now_hour)
                        if self.server.is_fork_active(self._now_hour) and br_send != br_pred_v:
                            xcut += 1
                            if (
                                self.cfg.p_drop_crosscut > 0
                                and self.drop_rng.random() < self.cfg.p_drop_crosscut
                            ):
                                xcut_drop += 1
                                continue

                        detected, proof_out, became_aware, became_evid = recv_gossip(
                            self.server,
                            v,
                            br_send,
                            ver_send,
                            self.branch,
                            self.version,
                            self.aware,
                            self.detector,
                            self._now_hour,
                            self.suspicion,
                            self.cfg.witness_required,
                            sth_period_hours=self.cfg.sth_period_hours,
                        )

                        bytes_tick += self.per_msg_bytes

                        if became_aware:
                            self.metrics.add_event(t, v, "aware")

                        if detected or became_evid:
                            # Backwards compatibility: keep "detect" too.
                            self.metrics.add_event(t, v, "evidence")
                            self.metrics.add_event(t, v, "detect")

                        if proof_out is not None:
                            if proof_out == ProofResult.OK:
                                pr_ok += 1
                            elif proof_out == ProofResult.INCONSISTENT:
                                pr_inc += 1
                            elif proof_out == ProofResult.WITHHOLD:
                                pr_withhold += 1
                            elif proof_out == ProofResult.TIMEOUT:
                                pr_timeout += 1

            # accumulate totals
            self.metrics.proof_ok += pr_ok
            self.metrics.proof_inconsistent += pr_inc
            self.metrics.proof_withhold += pr_withhold
            self.metrics.proof_timeout += pr_timeout
            self.metrics.crosscut_deliveries += xcut
            self.metrics.crosscut_dropped += xcut_drop

            self.metrics.add_bytes(bytes_tick)

            latest_br, latest_ver = self.server.latest_honest_sth(self._now_hour)
            latest_users = int(np.sum((self.branch == latest_br) & (self.version == latest_ver)))

            self.metrics.log_timeline(
                t,
                int(self.aware.sum()),
                int(self.detector.sum()),
                bytes_tick,
                pr_ok,
                pr_inc,
                pr_withhold,
                pr_timeout,
                xcut,
                xcut_drop,
                self.metrics.msgs_this_tick,
                latest_users, # new field for
            )
            self.metrics.msgs_this_tick = 0

        self.metrics.write(
            summary_extra={
                # config snapshot
                "users": self.n,
                "hours": self.cfg.hours,
                "dt_min": self.cfg.dt_min,
                "p_gossip": self.cfg.p_gossip,
                "mode": self.cfg.mode,
                "adoption": self.cfg.adoption,
                "avg_contacts": self.cfg.avg_contacts,
                "groups": self.cfg.groups,
                "avg_group_size": self.cfg.avg_group_size,
                # server behavior
                "server_mode": self.cfg.server_mode,
                "fork_hour": self.cfg.fork_hour,
                "fork_frac": self.cfg.fork_frac,
                "fork_duration": self.cfg.fork_duration,
                "sth_period_hours": self.cfg.sth_period_hours,
                "p_equiv": self.cfg.p_equiv,
                "proof_withhold_rate": self.cfg.proof_withhold_rate,
                "proof_timeout_rate": self.cfg.proof_timeout_rate,
                "invalid_proof_rate": self.cfg.invalid_proof_rate,
                "p_drop_crosscut": self.cfg.p_drop_crosscut,
                "crosscut_delivered": int(
                    self.metrics.crosscut_deliveries - self.metrics.crosscut_dropped
                ),
                "witness_required": self.cfg.witness_required,
            }
        )