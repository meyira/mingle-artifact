# Network Simulation

This Jupyter notebook contains the network simulation code used to evaluate the performance characteristics described in the paper.

## Quick Start

```bash
make
jupyter notebook
```
Then run all cells in order (Cell --> Run All).

## Configuration
Key parameters can be adjusted at the top of the notebook:
- `users` - Number of users (default small: 500, default laptop 2000)
- `hours` - Simulation duration
- `groups` - Number of group chats
- `msg_rate_1to1/group** - Message rates (TODO  messages per minute)
- `p\_gossip` - Probability of gossip protocol exchange
- `adoption` - Fraction of users using the gossip protocol
- `server\_mode` - mode of operation for the server, choose between honest, permanent\_fork, transient_fork, rolling, freeze, regional
- `fork\_hour` - When the server fork attack begins
- `fork\_frac` - Fraction of users affected by the fork

## Output

The simulation generates:
TODO  FILL IN HERE WHICH FIGURES ARE GENERATED HOW

Results match Figure 3 and Table 2 in the paper. TODO 

## Runtime

Expected runtime: under 10 minutes on a standard laptop.

To reduce runtime for testing, decrease `users` or `hours`.

## Troubleshooting

### Jupyter notebook won't start
Ensure Jupyter is installed: `pip install jupyter`

### Import errors
Make sure you've activated the virtual environment and installed all dependencies:
```bash
source .venv/bin/activate
.venv/bin/pip install --upgrade pip
pip install -r requirements.txt
```

### Simulation runs slowly
The simulation is computationally intensive. Consider:
- Reducing the number of users in the configuration
- Running on a machine with more CPU cores
- Using the pre-computed results in `network-simulation/results/` TODO  DO
  WE HAVE THESE?
