# Gossip PoC — In-band Gossip for Key Transparency (Signal-like)

This PoC simulates epidemic in-band gossip to disseminate KT data (STHs + optional consistency proofs)
across a messenger-style social graph. It includes:
- Realistic(ish) contact graph + group chats
- Diurnal activity windows
- Fork injection at the KT server (split-view)
- In-band gossip piggyback (STH-only or STH+proof)
- Metrics: TTD (time to first detection), dissemination coverage, overhead

## Quick start

### Linux/macOS (bash/zsh)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m sim.run --users 50000 --hours 24 --fork_hour 12 --mode sth_proof --p_gossip 0.6
python analysis/plot_results.py


python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m sim.run --users 50000 --hours 24 --fork_hour 12 --mode sth_proof --p_gossip 0.6
python analysis\plot_results.py

python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python -m sim.run --users 50000 --hours 24 --fork_hour 12 --mode sth_proof --p_gossip 0.6
python analysis\plot_results.py

Outputs in out/:

summary.json — TTD tick, totals, and config snapshot

timeline.csv — per-tick coverage & detectors (+ per-tick gossip bytes)

events.csv — detection events

coverage.png, detectors.png, gossip_bytes.png (plots)