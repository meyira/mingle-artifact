import numpy as np

def gen_contacts(n, avg_deg, rng, labels=None, p_cross: float = 1.0):
    """
    Generate a directed contact list per user.

    If labels is provided (bool/int array length n) and p_cross < 1.0, then contacts are generated with
    homophily w.r.t. the label cut:
      - with probability (1 - p_cross) choose a contact from the same label
      - with probability p_cross choose a contact from the opposite label

    This is a simple way to model 'targeted cohorts' that communicate mostly within themselves.
    """
    degs = rng.poisson(lam=avg_deg, size=n)
    degs = np.maximum(1, degs)

    if labels is None or p_cross >= 1.0:
        contacts = []
        for u in range(n):
            k = int(degs[u])
            sel = rng.choice(n-1, size=k, replace=False)
            sel = np.where(sel >= u, sel+1, sel)  # avoid self
            contacts.append(sel.astype(np.int32))
        return contacts

    labels = np.asarray(labels).astype(np.int8)
    idx0 = np.where(labels == 0)[0]
    idx1 = np.where(labels != 0)[0]
    contacts = []

    for u in range(n):
        k = int(degs[u])
        lu = labels[u]
        same_pool = idx0 if lu == 0 else idx1
        other_pool = idx1 if lu == 0 else idx0

        # sample counts
        k_cross = int(rng.binomial(k, min(max(p_cross, 0.0), 1.0)))
        k_same = k - k_cross

        # avoid self when sampling from same_pool
        if u in same_pool:
            same_pool_wo = same_pool[same_pool != u]
        else:
            same_pool_wo = same_pool

        # guard sizes
        k_same = min(k_same, len(same_pool_wo))
        k_cross = min(k_cross, len(other_pool))

        sel_same = rng.choice(same_pool_wo, size=k_same, replace=False) if k_same > 0 else np.array([], dtype=np.int64)
        sel_cross = rng.choice(other_pool, size=k_cross, replace=False) if k_cross > 0 else np.array([], dtype=np.int64)

        sel = np.concatenate([sel_same, sel_cross]).astype(np.int32)
        # If we undersampled (tiny pools), top up uniformly from all except self
        if len(sel) < k:
            need = k - len(sel)
            all_pool = np.arange(n, dtype=np.int64)
            all_pool = all_pool[all_pool != u]
            # avoid duplicates
            if len(sel) > 0:
                mask = np.ones_like(all_pool, dtype=bool)
                mask[np.isin(all_pool, sel)] = False
                all_pool = all_pool[mask]
            need = min(need, len(all_pool))
            if need > 0:
                sel2 = rng.choice(all_pool, size=need, replace=False).astype(np.int32)
                sel = np.concatenate([sel, sel2]).astype(np.int32)

        contacts.append(sel)
    return contacts


def gen_groups(n, groups, avg_size, rng, labels=None, p_cross: float = 1.0):
    """
    Generate group membership lists.

    If labels is provided and p_cross < 1.0, groups have a 'dominant' label chosen by sampling an anchor member.
    Remaining members are drawn mostly from the dominant label, with p_cross probability from the other label.
    """
    sizes = np.maximum(3, rng.poisson(lam=avg_size, size=groups))

    if labels is None or p_cross >= 1.0:
        members = []
        for g in range(groups):
            k = int(min(sizes[g], n))
            mem = rng.choice(n, size=k, replace=False)
            members.append(mem.astype(np.int32))
        user_groups = [[] for _ in range(n)]
        for gid, mem in enumerate(members):
            for u in mem:
                user_groups[u].append(gid)
        return members, user_groups

    labels = np.asarray(labels).astype(np.int8)
    idx0 = np.where(labels == 0)[0]
    idx1 = np.where(labels != 0)[0]

    members = []
    user_groups = [[] for _ in range(n)]
    p_cross = min(max(p_cross, 0.0), 1.0)

    for g in range(groups):
        k = int(min(sizes[g], n))

        # pick a dominant label via an anchor user sampled uniformly
        anchor = int(rng.integers(0, n))
        L = labels[anchor]
        same_pool = idx0 if L == 0 else idx1
        other_pool = idx1 if L == 0 else idx0

        k_cross = int(rng.binomial(k-1, p_cross))  # remaining after anchor
        k_same = (k-1) - k_cross

        # sample members
        # ensure anchor included
        mem = [anchor]

        # sample same-label (avoid duplicates / anchor)
        same_pool_wo = same_pool[same_pool != anchor]
        k_same = min(k_same, len(same_pool_wo))
        if k_same > 0:
            mem.extend(rng.choice(same_pool_wo, size=k_same, replace=False).tolist())

        # sample cross-label
        k_cross = min(k_cross, len(other_pool))
        if k_cross > 0:
            # avoid accidental duplicates (rare unless pools tiny)
            cand = other_pool
            if len(mem) > 0:
                cand = cand[~np.isin(cand, np.array(mem, dtype=np.int64))]
            k_cross = min(k_cross, len(cand))
            if k_cross > 0:
                mem.extend(rng.choice(cand, size=k_cross, replace=False).tolist())

        mem_arr = np.array(mem, dtype=np.int32)
        members.append(mem_arr)
        for u in mem_arr:
            user_groups[int(u)].append(g)

    return members, user_groups
