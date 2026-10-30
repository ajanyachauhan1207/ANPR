import sys
import importlib

try:
    cv2 = importlib.import_module("cv2")
except ImportError:
    cv2 = None

try:
    easyocr = importlib.import_module("easyocr")
    reader = easyocr.Reader(['en'], gpu=False)
except ImportError:
    reader = None

def find_plate(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    edges = cv2.Canny(gray, 30, 200)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]
    for c in contours:
        approx = cv2.approxPolyDP(c, 0.018 * cv2.arcLength(c, True), True)
        if len(approx) == 4:                      # 4 corners = rectangle
            x, y, w, h = cv2.boundingRect(approx)
            if 2 < w / h < 6:                     # plate-like shape
                return x, y, w, h
    return None

def read_plate(img):
    if reader is None:
        return None, None
    box = find_plate(img)
    if box is None:
        return None, None
    x, y, w, h = box
    crop = img[y:y + h, x:x + w]
    results = reader.readtext(crop)
    text = "".join(r[1] for r in results).upper().replace(" ", "")
    return text, box

def annotate(frame):
    text, box = read_plate(frame)
    if box:
        x, y, w, h = box
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(frame, text, (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    return frame

def run(source):
    if cv2 is None:
        raise RuntimeError("OpenCV is required. Install it with: pip install opencv-python")

    # Image file
    if source.lower().endswith((".jpg", ".jpeg", ".png")):
        img = annotate(cv2.imread(source))
        cv2.imshow("ANPR", img)
        cv2.waitKey(0)
        return
    # Webcam ("0") or video file
    cap = cv2.VideoCapture(0 if source == "0" else source)
    n = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        n += 1
        if n % 5 == 0:                            # process every 5th frame (faster)
            frame = annotate(frame)
        cv2.imshow("ANPR", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cap.release()

if __name__ == "__main__":
    run(sys.argv[1])