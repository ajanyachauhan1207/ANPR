import sys
import re
import cv2
import easyocr
from ultralytics import YOLO

model = YOLO("best.pt")
reader = easyocr.Reader(['en'], gpu=False)

ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
PATTERN = re.compile(r"^[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}$")
TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1",
            "Z": "2", "S": "5", "B": "8", "G": "6"}
TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}

def fix_format(t):
    n = len(t)
    if n < 9 or n > 11:
        return t
    chars = list(t)
    for i in range(n):
        if i < 2 or 4 <= i < n - 4:          # letter positions
            chars[i] = TO_LETTER.get(chars[i], chars[i])
        else:                                 # digit positions
            chars[i] = TO_DIGIT.get(chars[i], chars[i])
    return "".join(chars)

def variants(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    gray = cv2.copyMakeBorder(gray, 20, 20, 20, 20, cv2.BORDER_REPLICATE)
    yield gray
    yield cv2.createCLAHE(2.0, (8, 8)).apply(gray)
    yield cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

def ocr_best(crop):
    best = ""
    for v in variants(crop):
        texts = reader.readtext(v, detail=0, allowlist=ALLOWED)
        t = re.sub(r"[^A-Z0-9]", "", "".join(texts).upper())
        t = fix_format(t)
        if PATTERN.match(t):
            return t                          # looks like a valid plate
        if len(t) > len(best):
            best = t
    return best

def read_plates(img, fallback=True):
    found = []
    results = model.predict(img, conf=0.4, verbose=False)
    for box in results[0].boxes.xyxy:
        x1, y1, x2, y2 = map(int, box)
        found.append((ocr_best(img[y1:y2, x1:x2]), (x1, y1, x2, y2)))

    if not found and fallback:         # the image may be a cropped plate
        h, w = img.shape[:2]
        text = ocr_best(img)
        if len(text) >= 6:
            found.append((text, (0, 0, w, h)))
    return found

if __name__ == "__main__":
    img = cv2.imread(sys.argv[1])
    for text, (x1, y1, x2, y2) in read_plates(img):
        print("Plate:", text)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(img, text, (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    cv2.imwrite("output.jpg", img)
    cv2.imshow("ANPR", img)
    cv2.waitKey(0)