# Network Simulation

This Jupyter notebook contains the network simulation code used to evaluate the performance characteristics described in the paper.

The main artifact entry point is:

- `kt_gossip_simulator.ipynb`

This notebook reproduces the paper figures and tables from either:
1. cached outputs included in the repository (`quick reproduction`), or
2. raw simulation runs (`full reproduction`).

## Tested environment

Tested on:
- Windows 11

Tested with:
- Python 3.13

No GPU is required.
The simulations run on a standard laptop/desktop CPU.

## Repository structure

- `kt_gossip_simulator.ipynb`: canonical notebook for artifact evaluation
- `sim/`: simulator source code
- `analysis/`: helper analysis code used by the notebook
- `tools/`: utility code used by the notebook
- `out_nb_incremental_clean0104/`: cached outputs used for quick reproduction
- `requirements.txt`: Python dependencies


## Quick Start
# Windows Powershell
```powershell
py -3.13 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
jupyter lab kt_gossip_simulator.ipynb
```
### Linux/macOS

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
jupyter lab sims_paper_2104.ipynb
```

Then run all cells in order (Cell --> Run All).

## Configuration
Key parameters can be adjusted at the top of the notebook:
- `users` - Number of users (default small: 500, default laptop 2000)
- `hours` - Simulation duration
- `groups` - Number of group chats
- `msg_rate_1to1/group` - Message rates (TODO  messages per minute)
- `p\_gossip` - Probability of gossip protocol exchange
- `adoption` - Fraction of users using the gossip protocol
- `server\_mode` - mode of operation for the server, choose between honest, permanent\_fork, transient_fork, rolling, freeze, regional
- `fork\_hour` - When the server fork attack begins
- `fork\_frac` - Fraction of users affected by the fork

## Output

The simulation generates Plots for the 4 scenarios included in the paper: BASELINE, TRADEOFF, TARGET, CENSOR.


## Runtime

Expected runtime: under 10 minutes on a standard laptop.

To reduce runtime for testing, decrease `users` or `hours`.


### Simulation runs slowly
The simulation is computationally intensive. Consider:
- Reducing the number of users in the configuration
- Running on a machine with more CPU cores
## Quick reproduction
Quick reproduction regenerates the final paper figures/tables from the included cached outputs.

