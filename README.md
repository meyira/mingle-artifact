# Artifact for MINGLE

This artifact accompanies our submission **Chat as an Auditor: Gossip-Based Detection of Key Transparency Split Views in E2EE Messengers** and contains the complete materials necessary to reproduce and verify our experimental results.

## Contents

This artifact includes:

1. **Network Simulation** - Jupyter notebook containing the network simulation code
2. **User Study Data** - Complete results from our user studies (anonymized)
3. **Signal Client Proof of Concept** - Implementation code for the Signal client prototype

## Directory Structure

```
.
|-- README.md                         # This file
|-- network-simulation/
|   |-- analysis/                     # analysis scripts
|   |-- kt_gossip_simulator.ipynb     # Network simulation Jupyter notebook
|   |-- README.md                     # Simulation documentation
|-- user-study-results/
|   |-- results-user-study.csv        # Raw anonymized study data
|-- signal-gossip-client/
    |-- key-transparency-server/      # local KT server
    |-- libsignal/                    # Common Rust library for Signal apps.
    |-- Signal-Android/               # Signal Android App, relies on libsignal
    |-- requirements.txt              # Python dependencies
    |-- README.md                     # Implementation documentation
```

## Reproducing Paper Results

To reproduce the key results from our paper:

1. **User Study Results (Section 5.2):**
   - The results were analyzed by hand. Find the raw data under `user-study-results/analysis/analyze_results.py`.
   - Statistical tests will reproduce Table 3 and Figure 4

2. **Network Performance Results (Section 5.4):**
   - Run `network-simulation/simulation.ipynb`
   - Results will match Figure 3 and Table 2 in the paper

3. **Implementation Feasibility (Section 6):**
   - Review `signal-gossip-client/` implementation
   - Run test suite to verify functionality

## Changelog

- **v1.0** - Initial release for USENIX artifact evaluation
