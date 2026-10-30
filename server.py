import base64, csv, os, tempfile
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from flask import (Flask, jsonify, render_template, request, send_file,
                   send_from_directory)

import registry
from anpr_v2 import read_plates

app = Flask(__name__)
BASE = Path(__file__).parent
LOG = BASE / "detections.csv"
EVID = BASE / "evidence"
EVID.mkdir(exist_ok=True)
FIELDS = ["time", "plate", "source", "photo"]
registry.init_db()


def ensure_log():
    """Upgrade an old 3-column log so it also has a photo column."""
    if not LOG.exists():
        return
    with open(LOG, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)
    if "photo" in fields:
        return
    with open(LOG, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for r in rows:
            w.writerow([r.get(k) or "" for k in FIELDS])


ensure_log()


def save(plate, source, photo=""):
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(FIELDS)
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    plate, source, photo])


def save_photo(img, plate):
    """Save an evidence snapshot and return its file name."""
    h, w = img.shape[:2]
    if w > 900:
        img = cv2.resize(img, (900, int(h * 900 / w)))
    name = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{plate}.jpg"
    cv2.imwrite(str(EVID / name), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return name


def annotate(img, plates):
    out = img.copy()
    for text, (x1, y1, x2, y2) in plates:
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(out, text, (x1, max(y1 - 10, 25)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
    return out


def to_data_url(img):
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode()


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/api/image")
def api_image():
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file received"), 400
    img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return jsonify(error="Could not read that image"), 400
    plates = read_plates(img)
    annotated = annotate(img, plates)
    items = []
    for text, _ in plates:
        if text:
            save(text, "image", save_photo(annotated, text))
        items.append({"plate": text, "info": registry.lookup(text)})
    return jsonify(plates=items, image=to_data_url(annotated))


@app.post("/api/video")
def api_video():
    f = request.files.get("file")
    if not f:
        return jsonify(error="No file received"), 400
    step = int(request.form.get("step", 10))
    min_hits = int(request.form.get("min_hits", 2))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    f.save(tmp.name)
    tmp.close()

    cap = cv2.VideoCapture(tmp.name)
    counts, best = Counter(), {}
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            h, w = frame.shape[:2]
            if w > 960:
                frame = cv2.resize(frame, (960, int(h * 960 / w)))
            plates = read_plates(frame)
            for text, _ in plates:
                if len(text) >= 6:
                    counts[text] += 1
                    best[text] = annotate(frame, plates)
        i += 1
    cap.release()
    os.unlink(tmp.name)

    results = []
    for plate, c in counts.most_common():
        if c >= min_hits and len(results) < 5:
            save(plate, "video", save_photo(best[plate], plate))
            results.append({"plate": plate, "frames": c,
                            "info": registry.lookup(plate),
                            "image": to_data_url(best[plate])})
    return jsonify(results=results)


@app.get("/evidence/<path:name>")
def evidence(name):
    return send_from_directory(EVID, name)


@app.get("/api/vehicles")
def api_vehicles():
    return jsonify(registry.list_vehicles())


@app.post("/api/vehicles")
def api_add_vehicle():
    d = request.get_json(force=True)
    plate = registry.clean(d.get("plate", ""))
    if len(plate) < 6:
        return jsonify(error="Enter a valid plate number"), 400
    registry.add_vehicle(plate, d)
    return jsonify(ok=True)


@app.delete("/api/vehicles/<plate>")
def api_delete_vehicle(plate):
    registry.delete_vehicle(plate)
    return jsonify(ok=True)


def row_status(plate):
    i = registry.lookup(plate)
    if not i["found"]:
        return "Unknown"
    if i.get("status") and i["status"] != "Active":
        return "Flagged"
    if i.get("insurance_until") and i["insurance_until"] < datetime.now().date().isoformat():
        return "Insurance expired"
    return "Registered"


@app.get("/api/log")
def api_log():
    if not LOG.exists():
        return jsonify([])
    with open(LOG, newline="") as f:
        rows = list(csv.DictReader(f))

    q = request.args.get("q", "").strip().upper().replace(" ", "")
    start = request.args.get("from", "")
    end = request.args.get("to", "")
    want = request.args.get("status", "")

    cache, out = {}, []
    for row in rows:
        r = {k: (row.get(k) or "") for k in FIELDS}
        day = r["time"][:10]
        if q and q not in r["plate"]:
            continue
        if start and day < start:
            continue
        if end and day > end:
            continue
        if r["plate"] not in cache:
            cache[r["plate"]] = row_status(r["plate"])
        r["status"] = cache[r["plate"]]
        if want and r["status"] != want:
            continue
        out.append(r)
    return jsonify(out[::-1])


@app.get("/download")
def download():
    if not LOG.exists():
        return "No log yet", 404
    return send_file(LOG, as_attachment=True, download_name="detections.csv")


@app.post("/api/clear")
def api_clear():
    if LOG.exists():
        LOG.unlink()
    for p in EVID.glob("*.jpg"):
        p.unlink()
    return jsonify(ok=True)


@app.get("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.get("/api/stats")
def api_stats():
    rows = []
    if LOG.exists():
        with open(LOG, newline="") as f:
            rows = list(csv.DictReader(f))

    cache = {}

    def info(plate):
        if plate not in cache:
            cache[plate] = registry.lookup(plate)
        return cache[plate]

    today = datetime.now().date()
    per_day = Counter(r["time"][:10] for r in rows)
    daily = []
    for k in range(6, -1, -1):
        d = today - timedelta(days=k)
        daily.append({"day": d.strftime("%d %b"),
                      "count": per_day.get(d.isoformat(), 0)})

    registered = sum(1 for r in rows if info(r["plate"])["found"])

    top = []
    for plate, n in Counter(r["plate"] for r in rows).most_common(5):
        i = info(plate)
        top.append({"plate": plate, "count": n,
                    "owner": i["owner"] if i["found"] else "Not registered"})

    alerts = []
    for plate in sorted({r["plate"] for r in rows}):
        i = info(plate)
        if not i["found"]:
            continue
        if i.get("status") and i["status"] != "Active":
            alerts.append({"plate": plate, "owner": i["owner"],
                           "reason": "Flagged vehicle"})
        elif i.get("insurance_until") and i["insurance_until"] < today.isoformat():
            alerts.append({"plate": plate, "owner": i["owner"],
                           "reason": "Insurance expired"})

    return jsonify(total=len(rows),
                   unique=len({r["plate"] for r in rows}),
                   registered=registered,
                   unknown=len(rows) - registered,
                   daily=daily, top=top, alerts=alerts[:6])

import threading
import time

COOLDOWN = 60        # seconds a car must be out of view before it can be counted again
CONFIRM_HITS = 2     # frames a plate must appear in before it is counted
live_lock = threading.Lock()
live = {"seen": {}, "pending": {}, "count": 0}


def same_car(a, b):
    """True if two plate readings differ by at most one character."""
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b)) <= 1


def find_key(table, plate):
    for key in table:
        if same_car(key, plate):
            return key
    return None


def process_live(plates, img):
    now = time.time()
    events = []
    with live_lock:
        stale = [p for p, t in live["pending"].items() if now - t["last"] > 10]
        for p in stale:
            del live["pending"][p]

        for text, _ in plates:
            if len(text) < 6:
                continue
            key = find_key(live["seen"], text)
            if key and now - live["seen"][key] < COOLDOWN:
                live["seen"][key] = now              # still the same car
                continue

            pk = find_key(live["pending"], text)
            if pk is None:
                live["pending"][text] = {"hits": 1, "last": now,
                                         "votes": Counter([text])}
                continue

            item = live["pending"][pk]
            item["hits"] += 1
            item["last"] = now
            item["votes"][text] += 1
            if item["hits"] >= CONFIRM_HITS:
                final = item["votes"].most_common(1)[0][0]
                del live["pending"][pk]
                live["seen"][final] = now
                live["count"] += 1
                save(final, "live", save_photo(annotate(img, plates), final))
                events.append({"plate": final, "info": registry.lookup(final)})
        count = live["count"]
    return events, count


@app.post("/api/frame")
def api_frame():
    f = request.files.get("file")
    if not f:
        return jsonify(error="No frame received"), 400
    img = cv2.imdecode(np.frombuffer(f.read(), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return jsonify(error="Bad frame"), 400
    plates = read_plates(img, fallback=False)
    events, count = process_live(plates, img)
    boxes = [{"text": t, "box": list(b)} for t, b in plates]
    return jsonify(boxes=boxes, events=events, count=count)


@app.post("/api/live/reset")
def api_live_reset():
    with live_lock:
        live["seen"].clear()
        live["pending"].clear()
        live["count"] = 0
    return jsonify(ok=True)

if __name__ == "__main__":
    import threading, webbrowser
    threading.Timer(2.0, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="127.0.0.1", port=5000, debug=False)