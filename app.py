import hashlib
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from anpr_v2 import read_plates

st.set_page_config(page_title="ANPR", page_icon="🚗", layout="wide")
st.title("Automatic Number Plate Recognition")
st.caption("YOLOv8 plate detection + EasyOCR text reading")

LOG = Path("log.csv")


def save(plate):
    row = pd.DataFrame([{"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         "plate": plate}])
    row.to_csv(LOG, mode="a", header=not LOG.exists(), index=False)


def annotate(img, plates):
    out = img.copy()
    for text, (x1, y1, x2, y2) in plates:
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.putText(out, text, (x1, max(y1 - 10, 25)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
    return cv2.cvtColor(out, cv2.COLOR_BGR2RGB)


def process_video(path, step, min_hits):
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    bar = st.progress(0.0)
    preview = st.empty()
    counts, best = Counter(), {}
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            h, w = frame.shape[:2]
            if w > 960:                              # shrink big frames for speed
                frame = cv2.resize(frame, (960, int(h * 960 / w)))
            plates = read_plates(frame)
            for text, _ in plates:
                if len(text) >= 6:
                    counts[text] += 1
                    best[text] = annotate(frame, plates)
            preview.image(annotate(frame, plates), use_container_width=True)
        i += 1
        bar.progress(min(i / total, 1.0))
    cap.release()
    bar.empty()

    confirmed = [(p, c) for p, c in counts.most_common() if c >= min_hits]
    if not confirmed:
        st.warning("No plate was read reliably. Try a lower 'minimum frames' "
                   "value or a clearer video.")
        return
    st.success("Confirmed plates: " + ", ".join(p for p, _ in confirmed))
    st.dataframe(pd.DataFrame(confirmed, columns=["plate", "frames seen"]))
    for p, _ in confirmed[:5]:
        st.image(best[p], caption=p, use_container_width=True)
        save(p)


mode = st.radio("Input", ["Upload image", "Use camera", "Upload video"],
                horizontal=True)

if mode == "Upload video":
    vid = st.file_uploader("Choose a video", type=["mp4", "avi", "mov"])
    step = st.slider("Check every Nth frame (higher = faster)", 1, 30, 10)
    min_hits = st.slider("Minimum frames a plate must appear in", 1, 5, 2)
    if vid is not None and st.button("Process video"):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        tmp.write(vid.getvalue())
        tmp.close()
        process_video(tmp.name, step, min_hits)
else:
    if mode == "Upload image":
        file = st.file_uploader("Choose a car photo", type=["jpg", "jpeg", "png"])
    else:
        file = st.camera_input("Take a photo")

    if file is not None:
        raw = file.getvalue()
        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        with st.spinner("Reading plate..."):
            plates = read_plates(img)
        st.image(annotate(img, plates), use_container_width=True)
        if plates:
            st.success("Detected: " + ", ".join(t for t, _ in plates))
            h = hashlib.md5(raw).hexdigest()
            if st.session_state.get("last") != h:    # avoid duplicate log rows
                for t, _ in plates:
                    save(t)
                st.session_state["last"] = h
        else:
            st.warning("No plate found in this image.")

st.subheader("Detection log")
if LOG.exists():
    df = pd.read_csv(LOG)
    st.dataframe(df.iloc[::-1], use_container_width=True)
    st.download_button("Download log as CSV", df.to_csv(index=False), "log.csv")
else:
    st.info("No detections yet.")