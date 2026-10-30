import csv, random
from datetime import datetime, timedelta
import registry

registry.init_db()
plates = [v["plate"] for v in registry.list_vehicles()]
unknown = ["MH12XY9087", "GJ05CD2211", "RJ14AB7788"]
now = datetime.now()
random.seed(1)

rows = []
for _ in range(60):
    t = now - timedelta(days=random.randint(0, 6),
                        hours=random.randint(0, 10),
                        minutes=random.randint(0, 59))
    rows.append((t.strftime("%Y-%m-%d %H:%M:%S"),
                 random.choice(plates * 2 + unknown),
                 random.choice(["image", "video"])))
rows.sort()

with open("detections.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["time", "plate", "source"])
    w.writerows(rows)
print("Wrote", len(rows), "sample detections")