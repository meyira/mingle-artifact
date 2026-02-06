from dataclasses import dataclass
from enum import Enum, auto
import numpy as np

BRANCH_A, BRANCH_B = 0, 1

class ProofResult(Enum):
    OK = auto()
    INCONSISTENT = auto()   # cryptographic failure (evidence)
    WITHHOLD = auto()       # refuses to provide proof
    TIMEOUT = auto()        # rate-limit / delay


@dataclass
class ServerBehavior:
    # honest | permanent_fork | transient_fork | rolling | freeze | regional
    mode: str = "permanent_fork"
    fork_hour: float = 12.0
    fork_duration: float | None = None        # for transient_fork
    p_equiv: float = 0.0                      # for rolling (per-request equivocation prob)

    # Victim cohort behavior:
    # - sticky_victims=True: a fixed cohort sees branch B for the whole fork window
    # - sticky_victims=False: victim assignment varies over time (per epoch) for each user
    sticky_victims: bool = True
    fork_mask: np.ndarray | None = None       # optional fixed victims array (len N); used when sticky_victims=True

    # If fork_mask is provided, we infer fork_frac as mean(fork_mask).
    # If fork_mask is None, fork_frac provides the probability of being treated as a victim in non-sticky mode.
    fork_frac: float = 0.5

    # STH epoching
    sth_period_hours: float = 1.0

    # Proof faults / adversarial proof behavior
    proof_withhold_rate: float = 0.0
    proof_timeout_rate: float = 0.0
    invalid_proof_rate: float = 0.0           # return bad proof (detect instantly)

    # Witnessing model (optional)
    witness_required: bool = False            # if True, only branch A is considered witnessed

    # RNG seed
    rng_seed: int = 42


class Server:
    """
    KT server model with multiple behaviors:
    - current_sth(u, hour) -> (branch:int, epoch:int)
    - current_sth_info(u, hour) -> (branch:int, epoch:int, witness_ok:bool)
    - proof_response(old_sth, new_sth) -> ProofResult
    - is_fork_active(hour) -> bool

    Sticky victims:
      If b.sticky_victims=True and b.fork_mask is provided, user u is on branch B iff fork_mask[u] is True.
      If b.sticky_victims=False, the victim assignment varies by (user, epoch) using a deterministic hash,
      with probability p_victim. This makes the 'non-sticky' flag actually matter without needing to
      resample and store large masks over time.
    """
    def __init__(self, beh: ServerBehavior):
        self.b = beh
        self.rng = np.random.default_rng(beh.rng_seed)

        # infer victim probability if mask provided
        if self.b.fork_mask is not None:
            try:
                self._p_victim = float(np.mean(self.b.fork_mask))
            except Exception:
                self._p_victim = float(self.b.fork_frac)
        else:
            self._p_victim = float(self.b.fork_frac)

        # clamp
        self._p_victim = max(0.0, min(1.0, self._p_victim))

    # --- helpers ---
    def _epoch(self, hour: float) -> int:
        p = max(self.b.sth_period_hours, 1e-9)
        return int(hour / p)

    def is_fork_active(self, hour: float) -> bool:
        if self.b.mode == "honest":
            return False
        if hour < self.b.fork_hour:
            return False
        if self.b.mode == "transient_fork" and self.b.fork_duration is not None:
            return hour < (self.b.fork_hour + self.b.fork_duration)
        return True

    def _nonsticky_is_victim(self, u: int, epoch: int) -> bool:
        """
        Deterministic pseudo-random victim assignment based on (u, epoch, seed).
        This avoids storing per-epoch masks and ensures reproducible experiments.
        """
        # 32-bit mix (constants from LCG-ish hashing)
        x = (u * 2654435761 + epoch * 1013904223 + self.b.rng_seed * 1664525) & 0xFFFFFFFF
        r = x / 2**32  # in [0,1)
        return r < self._p_victim

    def _assign_branch(self, u: int, hour: float) -> int:
        if not self.is_fork_active(hour):
            return BRANCH_A

        if self.b.mode == "rolling":
            return BRANCH_B if self.rng.random() < self.b.p_equiv else BRANCH_A

        # permanent / transient / freeze / regional
        epoch = self._epoch(hour)

        if self.b.sticky_victims:
            if self.b.fork_mask is not None:
                # fixed cohort
                return BRANCH_B if bool(self.b.fork_mask[u]) else BRANCH_A
            # if sticky requested but no mask provided, fall back to deterministic by user only
            return BRANCH_B if self._nonsticky_is_victim(u, epoch=0) else BRANCH_A

        # non-sticky: vary by (user, epoch)
        return BRANCH_B if self._nonsticky_is_victim(u, epoch) else BRANCH_A

    # --- public API ---
    def current_sth(self, user_idx: int, hour: float):
        br = self._assign_branch(user_idx, hour)
        epoch = self._epoch(hour)

        # freeze: if user is currently on branch B, freeze their epoch at fork time
        if self.b.mode == "freeze" and br == BRANCH_B:
            epoch = self._epoch(self.b.fork_hour)

        return (br, epoch)

    def current_sth_info(self, user_idx: int, hour: float):
        br, epoch = self.current_sth(user_idx, hour)
        witness_ok = (not self.b.witness_required) or (br == BRANCH_A) or (not self.is_fork_active(hour))
        return (br, epoch, witness_ok)

    def proof_response(self, old_sth, new_sth) -> ProofResult:
        # Random operational failures / adversarial responses
        r = self.rng.random()
        if r < self.b.invalid_proof_rate:
            return ProofResult.INCONSISTENT

        r = self.rng.random()
        if r < self.b.proof_withhold_rate:
            return ProofResult.WITHHOLD

        r = self.rng.random()
        if r < self.b.proof_timeout_rate:
            return ProofResult.TIMEOUT

        # Normalize tuples to (br, epoch)
        br1, e1 = int(old_sth[0]), int(old_sth[1])
        br2, e2 = int(new_sth[0]), int(new_sth[1])

        # Cryptographic rule: append-only is OK iff same branch & non-decreasing epoch
        if br1 == br2 and e2 >= e1:
            return ProofResult.OK
        return ProofResult.INCONSISTENT


# Backward-compatible alias for older scripts
ServerConfig = ServerBehavior
