
## `Makefile` (optional)
VENV = .venv
PY = $(VENV)/bin/python

all: demo

venv:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

demo: venv
	$(PY) -m sim.run --users 50000 --hours 24 --fork_hour 12 --mode sth_proof --p_gossip 0.6
	$(PY) analysis/plot_results.py

clean:
	rm -rf $(VENV) out __pycache__ sim/__pycache__ analysis/__pycache__
