from dataclasses import dataclass

@dataclass
class SimConfig:
    # Scale & time
    users: int = 100_000
    hours: float = 24
    dt_min: int = 5

    # Graph & groups
    avg_contacts: int = 25
    groups: int = 20_000
    avg_group_size: int = 12

    # Network mixing across the victim/non-victim cut (for targeted-fork scenarios)
    # p_contact_cross: probability that a contact edge is chosen across the cut (victim<->non-victim).
    # p_group_cross: probability that a group member is sampled across the cut (mixing within groups).
    # Set these low (e.g., 0.01–0.1) to model a socially clustered targeted cohort.
    p_contact_cross: float = 1.0
    p_group_cross: float = 1.0

    # User behavior
    active_hour_mu: float = 20.5  # ~8:30 PM
    active_hour_sigma: float = 3.0
    active_span_hours: float = 14.0
    msg_rate_1to1: float = 0.10
    msg_rate_group: float = 0.06

    # Gossip
    mode: str = "sth_proof"       # 'sth_only' or 'sth_proof'
    p_gossip: float = 0.6
    sth_bytes: int = 128
    proof_bytes: int = 768
    adoption: float = 0.8

    # Server behavior (NEW)
    server_mode: str = "permanent_fork"    # honest | permanent_fork | transient_fork | rolling | freeze | regional
    fork_hour: float = 12.0
    fork_frac: float = 0.5
    fork_duration: float | None = None     # for transient_fork
    sth_period_hours: float = 1.0
    p_equiv: float = 0.0                    # rolling equivocation probability
    sticky_victims: bool = True
    proof_withhold_rate: float = 0.0
    proof_timeout_rate: float = 0.0
    invalid_proof_rate: float = 0.0
    p_drop_crosscut: float = 0.0            # drop prob for A<->B deliveries (suppression)
    witness_required: bool = False
    
    # NEW: audits & suspicion policy
    p_self_audit: float = 0.02       # per active tick, user audits own entry (~ occasional)
    p_anon_check: float = 0.02       # per active tick, user anonymously samples STR
    suspicion_threshold: int = 3     # after this many soft failures, escalate checks
    suspicion_decay: float = 0.5     # subtract each hour (in “points”)
    penalty_withhold: int = 1        # suspicion increment when proof withheld
    penalty_timeout: int = 1         # suspicion increment when proof timeouts
    # Random seed
    seed: int = 42

    # Output
    outdir: str = "out"
