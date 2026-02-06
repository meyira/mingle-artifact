#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m sim.run --users 50000 --hours 24 --fork_hour 12 --mode sth_proof --p_gossip 0.6
python analysis/plot_results.py
