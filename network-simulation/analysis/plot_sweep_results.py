
import matplotlib
matplotlib.use("TkAgg")

import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("out_sweeps/all_summaries.csv")

# Keep only permanent fork baseline
df = df[df["server_mode"] == "permanent_fork"]

# Convert ticks to minutes
df["detection_min"] = df["first_detection_tick"] * df["dt_min"]

# Plot
plt.figure()
df.boxplot(column="detection_min", by="p_gossip")
plt.title("Detection latency vs gossip probability")
plt.suptitle("")
plt.xlabel("p_gossip")
plt.ylabel("Minutes to first detection")
plt.tight_layout()
plt.savefig("out_sweeps/detection_vs_pgossip.png")
plt.show()


plt.show(block=True)