import json, csv
import matplotlib.pyplot as plt

# Load timeline
ticks, aware, det, bytes_tick = [], [], [], []
with open('out/timeline.csv', newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        ticks.append(int(row['tick']))
        aware.append(int(row['aware_users']))
        det.append(int(row['detectors']))
        bytes_tick.append(int(row['gossip_bytes_this_tick']))

# Summary/config
with open('out/summary.json', encoding='utf-8') as f:
    summary = json.load(f)

dt_min = summary['dt_min']; users = summary['users']

# Coverage
plt.figure()
plt.plot([t*dt_min/60 for t in ticks], [a/users for a in aware])
plt.title('Dissemination Coverage (aware/users)')
plt.xlabel('Time (hours)'); plt.ylabel('Coverage fraction'); plt.grid(True)
plt.tight_layout(); plt.savefig('out/coverage.png', dpi=150)

# Detectors
plt.figure()
plt.plot([t*dt_min/60 for t in ticks], det)
plt.title('Detectors Over Time')
plt.xlabel('Time (hours)'); plt.ylabel('# Detectors'); plt.grid(True)
plt.tight_layout(); plt.savefig('out/detectors.png', dpi=150)

# Bytes per tick
plt.figure()
plt.plot([t*dt_min/60 for t in ticks], bytes_tick)
plt.title('Gossip Bytes Sent Per Tick')
plt.xlabel('Time (hours)'); plt.ylabel('Bytes/tick'); plt.grid(True)
plt.tight_layout(); plt.savefig('out/gossip_bytes.png', dpi=150)

print("Saved plots: out/coverage.png, out/detectors.png, out/gossip_bytes.png")
print("First detection tick:", summary['first_detection_tick'],
      "=> minutes:", (summary['first_detection_tick']*dt_min
                      if summary['first_detection_tick'] is not None else None))
