"""
Live animation of in-band gossip propagation across the social graph.

Usage (Windows PowerShell w/out activation):
  .\.venv\Scripts\python.exe analysis\animate_gossip.py --users 400 --hours 6 --dt_min 2 ^
    --avg_contacts 6 --msg_rate_1to1 0.25 ^
    --fork_hour 2 --fork_frac 0.5 --adoption 1.0 --p_gossip 1.0

Tip: start small (N=300–800). Layout dominates time if N is huge.
"""
import sys
import os
import argparse
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.gridspec import GridSpec
import networkx as nx

# Get the parent directory (project root)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Add it to sys.path
sys.path.append(project_root)

# Import the PoC modules
from sim.config import SimConfig
from sim.graph import gen_contacts, gen_groups
from sim.server import Server, ServerConfig
from sim.client_logic import recv_gossip


class RealtimeSim:
    """
    A tick-by-tick version of the PoC simulator focused on interactivity.
    Defaults to 1:1 messages (groups optional but off by default for clarity).
    """
    def __init__(self, cfg: SimConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self.n = cfg.users

        # Activity windows
        self.active_start, self.active_end = self._sample_active_window(
            self.n, cfg.active_hour_mu, cfg.active_hour_sigma, cfg.active_span_hours
        )
        self.adopts = self.rng.random(self.n) < cfg.adoption

        # Social graph
        self.contacts = gen_contacts(self.n, cfg.avg_contacts, self.rng)
        self.groups, self.user_groups = gen_groups(self.n, cfg.groups, cfg.avg_group_size, self.rng) if cfg.groups > 0 else ([], [[] for _ in range(self.n)])

        # KT client state
        self.version = np.zeros(self.n, dtype=np.int32)   # last version seen
        self.branch  = np.zeros(self.n, dtype=np.int8)    # 0=A, 1=B
        self.aware   = np.zeros(self.n, dtype=bool)       # saw any STH yet
        self.detect  = np.zeros(self.n, dtype=bool)       # detected fork

        # Fork cohort
        self.fork_mask = (self.rng.random(self.n) < cfg.fork_frac)

        # Server
        self.server = Server(ServerConfig(fork_hour=cfg.fork_hour, fork_mask=self.fork_mask))

        # Time bookkeeping
        self.ticks_total = int(cfg.hours * 60 / cfg.dt_min)
        self.now_hour = 0.0

        # Gossip payload sizing (for reference; not used in animation)
        self.per_msg_bytes = cfg.sth_bytes + (cfg.proof_bytes if cfg.mode == "sth_proof" else 0)

    # ==== helpers ====
    def _sample_active_window(self, n, mu, sigma, span_mean):
        span = np.maximum(8.0, self.rng.normal(loc=span_mean, scale=1.5, size=n))
        start = self.rng.normal(loc=mu - span/2, scale=sigma, size=n)
        start = np.mod(start, 24.0)
        end = (start + span) % 24.0
        return start, end

    @staticmethod
    def _in_window(t_hour, start, end):
        return (t_hour >= start and t_hour < end) if start <= end else not (t_hour >= end and t_hour < start)

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
        # group (optional; off by default unless you set --groups > 0)
        if self.cfg.groups > 0 and self.rng.random() < self.cfg.msg_rate_group and len(self.user_groups[u]) > 0:
            gid = int(self.rng.choice(self.user_groups[u]))
            deliveries.append(self.groups[gid])
        return deliveries

    def _refresh_to_current_sth(self, u):
        """Keep user in sync with server epoch; surfaces fork branches post-fork."""
        cur_ver = int(self.now_hour)
        if self.version[u] == 0 or self.version[u] < cur_ver:
            br, ver = self.server.current_sth(u, self.now_hour)
            self.branch[u], self.version[u] = br, ver

    def _attach_sth(self, u):
        self._refresh_to_current_sth(u)
        return int(self.branch[u]), int(self.version[u])

    # ==== one tick ====
    def step(self, tick_idx: int):
        self.now_hour = (tick_idx * self.cfg.dt_min) / 60.0

        # Choose active users
        active = [u for u in range(self.n) if self._is_active(u, self.now_hour)]

        # Send messages & gossip
        for u in active:
            deliveries = self._maybe_send(u)
            for dst_arr in deliveries:
                if self.adopts[u] and (self.rng.random() < self.cfg.p_gossip):
                    br, ver = self._attach_sth(u)
                    for v in dst_arr:
                        _detected = recv_gossip(
                            self.server, int(v), br, ver,
                            self.branch, self.version, self.aware, self.detect,
                            self.now_hour
                        )

        # Return a view of the current state for drawing
        return self.branch.copy(), self.version.copy(), self.aware.copy(), self.detect.copy(), np.array(active, dtype=int)


def build_nx_graph(sim: RealtimeSim, max_edges: int = 20000):
    """
    Convert directed contacts to an undirected simple graph for visualization.
    If edges exceed max_edges, subsample to keep the plot smooth.
    """
    G = nx.Graph()
    G.add_nodes_from(range(sim.n))
    # Build edges; keep it light
    edges = set()
    for u in range(sim.n):
        for v in sim.contacts[u]:
            a, b = (int(u), int(v))
            if a == b: 
                continue
            if a > b:
                a, b = b, a
            edges.add((a, b))
            if len(edges) >= max_edges:
                break
        if len(edges) >= max_edges:
            break
    G.add_edges_from(edges)
    return G


def colormap(branch, version, aware, detect):
    """
    Map per-node state to colors and edgecolors.
    - unaware: light gray
    - branch A: blue
    - branch B: orange
    - detectors: red edge
    """
    colors = []
    edgecols = []
    for i in range(len(branch)):
        if not aware[i] or version[i] == 0:
            colors.append("#d3d3d3")  # light gray
        else:
            colors.append("#1f77b4" if branch[i] == 0 else "#ff7f0e")  # blue / orange
        edgecols.append("#d62728" if detect[i] else "black")  # red edge if detector
    return colors, edgecols


def animate(cfg: SimConfig, save_path: str | None):
    # Build realtime sim
    sim = RealtimeSim(cfg)

    # NetworkX layout (spring). For >1000 nodes, this can be slow; try --users 400 first.
    G = build_nx_graph(sim)
    pos = nx.spring_layout(G, seed=cfg.seed, k=None)

    # === Figure with side panel ===
    fig = plt.figure(figsize=(12, 6.8))
    gs = GridSpec(2, 3, figure=fig, width_ratios=[2.2, 1.0, 1.0], height_ratios=[1.0, 1.0])
    ax_graph = fig.add_subplot(gs[:, 0])          # big left pane
    ax_cov   = fig.add_subplot(gs[0, 1:])         # top-right: coverage
    ax_det   = fig.add_subplot(gs[1, 1:])         # bottom-right: detectors

    ax_graph.set_title("In-band gossip propagation (live)")
    ax_graph.axis("off")

    # Initial draw (graph)
    branch, version, aware, detect, active = sim.branch, sim.version, sim.aware, sim.detect, np.array([], dtype=int)
    node_colors, node_edgecols = colormap(branch, version, aware, detect)
    xy = np.array([pos[i] for i in range(sim.n)])
    sc = ax_graph.scatter(xy[:, 0], xy[:, 1], s=20, c=node_colors, edgecolors=node_edgecols, linewidths=0.6)

    # Active overlay (purple rings)
    active_sc = ax_graph.scatter([], [], s=35, facecolors='none', edgecolors='#9467bd', linewidths=1.0, alpha=0.9)
    active_sc.set_visible(True)

    # Legend
    from matplotlib.lines import Line2D
    legend_elems = [
        Line2D([0], [0], marker='o', color='w', label='Unaware', markerfacecolor='#d3d3d3', markersize=8, markeredgecolor='black'),
        Line2D([0], [0], marker='o', color='w', label='Branch A', markerfacecolor='#1f77b4', markersize=8, markeredgecolor='black'),
        Line2D([0], [0], marker='o', color='w', label='Branch B', markerfacecolor='#ff7f0e', markersize=8, markeredgecolor='black'),
        Line2D([0], [0], marker='o', color='w', label='Detector (edge)', markerfacecolor='white', markeredgecolor='#d62728', markersize=8, linewidth=2),
        Line2D([0], [0], marker='o', color='w', label='Active (ring)', markerfacecolor='white', markeredgecolor='#9467bd', markersize=8, linewidth=2),
    ]
    ax_graph.legend(handles=legend_elems, loc="upper right", frameon=False)

    # === Side-panel plots ===
    total_hours = cfg.hours
    xs = []               # time (hours)
    cov_vals = []         # coverage fraction
    det_vals = []         # # detectors

    # Coverage plot
    cov_line, = ax_cov.plot([], [], linewidth=1.5)
    ax_cov.set_title("Coverage (aware / users)")
    ax_cov.set_xlim(0, total_hours)
    ax_cov.set_ylim(0, 1)
    ax_cov.grid(True, alpha=0.3)
    ax_cov.axvline(cfg.fork_hour, linestyle="--", linewidth=1.0)

    # Detectors plot
    det_line, = ax_det.plot([], [], linewidth=1.5)
    ax_det.set_title("Detectors")
    ax_det.set_xlim(0, total_hours)
    ax_det.set_ylim(0, max(10, int(sim.n * 0.1)))  # start with a small headroom; we'll autoscale up
    ax_det.grid(True, alpha=0.3)
    ax_det.axvline(cfg.fork_hour, linestyle="--", linewidth=1.0)

    # Footer stats
    text = ax_graph.text(0.02, 0.02, "", transform=ax_graph.transAxes, fontsize=9, va="bottom", ha="left")

    def update(frame_idx):
        # Step simulation
        branch, version, aware, detect, active = sim.step(frame_idx)

        # Update graph colors
        node_colors, node_edgecols = colormap(branch, version, aware, detect)
        sc.set_facecolors(node_colors)
        sc.set_edgecolors(node_edgecols)

        # Active overlay
        if len(active) > 0:
            active_xy = xy[active]
            active_sc.set_offsets(active_xy)
            active_sc.set_visible(True)
        else:
            active_sc.set_visible(False)

        # Time & stats
        hour = (frame_idx * cfg.dt_min) / 60.0
        aware_cnt = int(aware.sum())
        det_cnt = int(detect.sum())
        text.set_text(f"tick={frame_idx}/{sim.ticks_total} | hour={hour:.2f} | aware={aware_cnt} | detectors={det_cnt}")

        # Update side plots
        xs.append(hour)
        cov_vals.append(aware_cnt / sim.n)
        det_vals.append(det_cnt)

        cov_line.set_data(xs, cov_vals)
        det_line.set_data(xs, det_vals)

        # Keep x-limits stable [0, total_hours]; auto-scale detectors y if needed
        if det_cnt > ax_det.get_ylim()[1] * 0.95:
            ax_det.set_ylim(0, max(det_cnt * 1.2, 10))

        # Stop at end
        if frame_idx + 1 >= sim.ticks_total:
            anim.event_source.stop()

        return sc, active_sc, cov_line, det_line, text

    anim = FuncAnimation(fig, update, frames=sim.ticks_total, interval=150, blit=False, repeat=False)
    plt.tight_layout()

    if save_path:
        # Choose writer based on extension
        ext = save_path.lower().rsplit(".", 1)[-1]
        try:
            if ext == "mp4":
                from matplotlib.animation import FFMpegWriter
                writer = FFMpegWriter(fps=max(2, int(60_000 / (cfg.dt_min * 1000))), bitrate=1800)
                anim.save(save_path, writer=writer)
            elif ext == "gif":
                from matplotlib.animation import PillowWriter
                anim.save(save_path, writer=PillowWriter(fps=6))
            else:
                print(f"[warn] Unknown extension '.{ext}', not saving.")
        except Exception as e:
            print(f"[warn] Could not save animation: {e}")

    plt.show()


def main():
    import argparse
    ap = argparse.ArgumentParser()
    # scale/time
    ap.add_argument("--users", type=int, default=400)
    ap.add_argument("--hours", type=float, default=6)
    ap.add_argument("--dt_min", type=int, default=2)
    # graph/traffic
    ap.add_argument("--avg_contacts", type=int, default=6)
    ap.add_argument("--groups", type=int, default=0)
    ap.add_argument("--avg_group_size", type=int, default=8)
    ap.add_argument("--msg_rate_1to1", type=float, default=0.25)
    ap.add_argument("--msg_rate_group", type=float, default=0.06)
    # gossip
    ap.add_argument("--mode", choices=["sth_only","sth_proof"], default="sth_proof")
    ap.add_argument("--p_gossip", type=float, default=1.0)
    ap.add_argument("--sth_bytes", type=int, default=128)
    ap.add_argument("--proof_bytes", type=int, default=768)
    ap.add_argument("--adoption", type=float, default=1.0)
    # server behavior (NEW)
    ap.add_argument("--server_mode", type=str, default="permanent_fork",
                    choices=["honest","permanent_fork","transient_fork","rolling","freeze","regional"])
    ap.add_argument("--fork_hour", type=float, default=2.0)
    ap.add_argument("--fork_frac", type=float, default=0.5)
    ap.add_argument("--fork_duration", type=float, default=None)
    ap.add_argument("--sth_period_hours", type=float, default=1.0)
    ap.add_argument("--p_equiv", type=float, default=0.0)
    ap.add_argument("--witness_required", action="store_true", default=False)
    # misc
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--save", type=str, default=None, help="Optional path to save (mp4/gif)")
    args = ap.parse_args()

    from sim.config import SimConfig
    cfg = SimConfig(
        users=args.users, hours=args.hours, dt_min=args.dt_min,
        avg_contacts=args.avg_contacts, groups=args.groups, avg_group_size=args.avg_group_size,
        active_hour_mu=20.5, active_hour_sigma=3.0, active_span_hours=14.0,
        msg_rate_1to1=args.msg_rate_1to1, msg_rate_group=args.msg_rate_group,
        mode=args.mode, p_gossip=args.p_gossip, sth_bytes=args.sth_bytes, proof_bytes=args.proof_bytes,
        adoption=args.adoption,
        server_mode=args.server_mode, fork_hour=args.fork_hour, fork_frac=args.fork_frac,
        fork_duration=args.fork_duration, sth_period_hours=args.sth_period_hours,
        p_equiv=args.p_equiv, sticky_victims=True,
        proof_withhold_rate=0.0, proof_timeout_rate=0.0, invalid_proof_rate=0.0,
        p_drop_crosscut=0.0, witness_required=args.witness_required,
        seed=args.seed, outdir="out"
    )
    animate(cfg, save_path=args.save)

if __name__ == "__main__":
    main()
