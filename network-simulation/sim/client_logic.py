import numpy as np
from .server import ProofResult

def recv_gossip(
    server,
    u: int,
    br_in: int,
    ver_in: int,
    branch_arr: np.ndarray,
    version_arr: np.ndarray,
    aware_arr: np.ndarray,
    evidence_arr: np.ndarray,
    now_hour: float,
    suspicion_arr: np.ndarray | None = None,
    witness_required: bool = False,
    sth_period_hours: float | None = None,
):
    """Process an incoming gossip commitment (br_in, ver_in) for user u.

    Maintains two layers of client state:

    - Awareness (soft): client has *observed a conflicting view* (e.g., branch mismatch,
      proof failure/withhold/timeout). Awareness is intended to be *epidemic*: it should
      spread even if the client has not yet obtained a cryptographic proof.
    - Evidence (strict): client has obtained cryptographic evidence (INCONSISTENT proof).

    Returns:
      (detected_strict, proof_result, became_aware, became_evidence)
    """
    proof_out = None

    # Determine current STH epoch/period for refresh.
    if sth_period_hours is None or sth_period_hours <= 0:
        cur_epoch = int(now_hour)
    else:
        cur_epoch = int(now_hour / sth_period_hours)

    # Refresh receiver to server's current view for this epoch if stale.
    if version_arr[u] == 0 or version_arr[u] < cur_epoch:
        br0, v0 = server.current_sth(u, now_hour)
        branch_arr[u], version_arr[u] = br0, v0

    br_u, ver_u = int(branch_arr[u]), int(version_arr[u])

    was_aware = bool(aware_arr[u])
    was_evid  = bool(evidence_arr[u])

    # Helper: mark soft awareness + optional suspicion increment
    def mark_aware():
        aware_arr[u] = True
        if suspicion_arr is not None:
            suspicion_arr[u] = min(2**31 - 1, int(suspicion_arr[u]) + 1)

    # === Case 1: Same branch (potentially newer version) ===
    if br_in == br_u:
        if ver_in > ver_u:
            proof_out = server.proof_response((br_u, ver_u), (br_in, ver_in))

            if proof_out == ProofResult.OK:
                # benign evolution: update local version; no awareness.
                version_arr[u] = ver_in

            elif proof_out == ProofResult.INCONSISTENT:
                # strict evidence
                evidence_arr[u] = True
                aware_arr[u] = True
            else:
                # WITHHOLD or TIMEOUT (soft signal)
                mark_aware()
        # else: equal/older -> ignore

    # === Case 2: Branch mismatch ===
    else:
        # Soft awareness should trigger immediately upon receiving a conflicting branch.
        # This is the *epidemic* signal: users can become aware without holding a proof.
        mark_aware()

        # Optionally attempt to obtain strict evidence by requesting a (cross-branch)
        # consistency proof. In an equivocation/fork scenario this should fail (INCONSISTENT)
        # if the server is honest about its inability to link forks, or be WITHHOLD/TIMEOUT
        # under suppression.
        proof_out = server.proof_response((br_u, ver_u), (br_in, ver_in))

        if proof_out == ProofResult.INCONSISTENT:
            evidence_arr[u] = True
        elif proof_out in (ProofResult.WITHHOLD, ProofResult.TIMEOUT):
            # already aware; keep as soft signal
            pass
        elif proof_out == ProofResult.OK:
            # Some models may allow reconciling views; update to the newer view if needed.
            # (This shouldn't happen for true forks.)
            # We conservatively accept the higher version within the received branch.
            branch_arr[u] = br_in
            version_arr[u] = max(ver_u, ver_in)

    # Optional: witness-required violations could be modeled here if payload carries witness bits.
    if witness_required:
        # If you later add witness fields, mark awareness (and potentially evidence) here.
        pass

    became_aware = (not was_aware) and bool(aware_arr[u])
    became_evid  = (not was_evid)  and bool(evidence_arr[u])
    detected_strict = became_evid

    return detected_strict, proof_out, became_aware, became_evid
