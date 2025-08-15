# deps: pip install mss opencv-python pytesseract numpy
# Install Tesseract engine. On Windows, set the path if needed:
# from pytesseract import pytesseract
# pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

import numpy as np
import cv2
import mss
import re
from typing import Dict, List, Tuple, Optional
from pytesseract import image_to_data, Output

MIN_CONF = 0
UPSCALE = 1.9 
BOTTOM_BAND = 0.2 

# -------------------- Capture --------------------
def capture_screen(monitor_index: int = 1) -> np.ndarray:
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[monitor_index])   # BGRA
        return np.array(raw)[:, :, :3].copy()         # BGR

def preprocess_for_ocr(img_bgr: np.ndarray, invert_if_dark=True, upscale=UPSCALE,
                       binarize: Optional[str] = "otsu") -> np.ndarray:
    if upscale and upscale != 1.0:
        img_bgr = cv2.resize(img_bgr, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    if invert_if_dark and float(np.mean(gray)) < 127:
        gray = cv2.bitwise_not(gray)

    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

    if binarize == "otsu":
        return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    elif binarize == "adaptive":
        return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 31, 5)
    else:
        return gray

def _image_to_data_with_offset(img_gray: np.ndarray, cfg: str, offset_xy=(0, 0)) -> Dict[str, List]:
    data = image_to_data(img_gray, output_type=Output.DICT, config=cfg, lang="eng")
    offx, offy = offset_xy
    for i in range(len(data["text"])):
        data["left"][i] += offx
        data["top"][i]  += offy
    return data

def run_ocr(img_bgr: np.ndarray, *, psm: int = 11, dpi: int = 220,
            whitelist: Optional[str] = None, roi: Optional[Tuple[int,int,int,int]] = None) -> Dict[str, List]:
    if roi:
        x, y, w, h = roi
        sub = img_bgr[y:y+h, x:x+w]
        prep = preprocess_for_ocr(sub)
        cfg  = f"--oem 3 --psm {psm} -c preserve_interword_spaces=1 -c user_defined_dpi={dpi}"
        if whitelist:
            cfg += f" -c tessedit_char_whitelist={whitelist}"
        return _image_to_data_with_offset(prep, cfg, offset_xy=(x, y))
    else:
        prep = preprocess_for_ocr(img_bgr)
        cfg  = f"--oem 3 --psm {psm} -c preserve_interword_spaces=1 -c user_defined_dpi={dpi}"
        if whitelist:
            cfg += f" -c tessedit_char_whitelist={whitelist}"
        return image_to_data(prep, output_type=Output.DICT, config=cfg, lang="eng")

def merge_ocr_dicts(a: Dict[str, List], b: Dict[str, List]) -> Dict[str, List]:
    if not a: return b
    if not b: return a
    out = {}
    for k in a.keys():
        out[k] = a[k] + b[k]
    return out

def _build_lines(ocr: dict, min_conf: int = MIN_CONF):
    lines = {}
    N = len(ocr["text"])
    for i in range(N):
        txt = (ocr["text"][i] or "").strip()
        if not txt:
            continue
        try:
            conf = float(ocr["conf"][i])
        except Exception:
            conf = 0.0
        if conf < min_conf:
            continue
        x, y, w, h = ocr["left"][i], ocr["top"][i], ocr["width"][i], ocr["height"][i]
        key = (ocr["block_num"][i], ocr["par_num"][i], ocr["line_num"][i])
        tok = {"text": txt, "conf": conf, "box": (x, y, w, h)}
        if key not in lines:
            lines[key] = {"text": txt, "tokens": [tok], "x1": x, "y1": y, "x2": x + w, "y2": y + h}
        else:
            L = lines[key]
            L["text"] += ("" if L["text"].endswith(" ") else " ") + txt
            L["tokens"].append(tok)
            L["x1"], L["y1"] = min(L["x1"], x), min(L["y1"], y)
            L["x2"], L["y2"] = max(L["x2"], x + w), max(L["y2"], y + h)
    out = []
    for L in lines.values():
        idx = 0
        for t in L["tokens"]:
            s = L["text"].find(t["text"], idx)
            if s < 0: s = L["text"].find(t["text"])
            e = s + len(t["text"])
            t["span"] = (s, e)
            idx = e + 1
        out.append({
            "text": L["text"],
            "line_box": (L["x1"], L["y1"], L["x2"] - L["x1"], L["y2"] - L["y1"]),
            "tokens": L["tokens"]
        })
    return out

def extract_text_list(ocr: dict, min_conf: int = MIN_CONF):
    lines = _build_lines(ocr, min_conf=min_conf)
    return [L["text"] for L in lines]

def find_text_boxes(ocr: dict, query: str, *, case_sensitive=False, whole_word=False, min_conf: int = MIN_CONF):
    if not query:
        return []
    lines = _build_lines(ocr, min_conf=min_conf)
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = r"\b" + re.escape(query) + r"\b" if whole_word else re.escape(query)
    rx = re.compile(pattern, flags)
    boxes = []
    for L in lines:
        line_text = L["text"] if case_sensitive else L["text"].lower()
        for m in rx.finditer(line_text):
            s, e = m.span()
            token_boxes = []
            for t in L["tokens"]:
                ts, te = t["span"]
                if te <= s or ts >= e:
                    continue
                token_boxes.append(t["box"])
            if not token_boxes:
                boxes.append(L["line_box"])
            else:
                token_boxes.sort(key=lambda b: b[0])
                merged = [token_boxes[0]]
                for x, y, w, h in token_boxes[1:]:
                    px, py, pw, ph = merged[-1]
                    if x <= px + pw + 6 and abs(y - py) < max(h, ph):
                        nx1, ny1 = min(px, x), min(py, y)
                        nx2, ny2 = max(px + pw, x + w), max(py + ph, y + h)
                        merged[-1] = (nx1, ny1, nx2 - nx1, ny2 - ny1)
                    else:
                        merged.append((x, y, w, h))
                boxes.extend(merged)
    return boxes

# -------------------- EXAMPLE RUN --------------------
if __name__ == "__main__":

    img = capture_screen(monitor_index=1)
    H, W = img.shape[:2]
    print(f"[OK] Captured screen: {W}x{H}")

    ocr_all = run_ocr(img, psm=11)

    band_h = int(H * BOTTOM_BAND)
    roi = (0, H - band_h, W, band_h)
    
    
    ocr_band = run_ocr(
        img, psm=7,
        whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",
        roi=roi
    )


    ocr = merge_ocr_dicts(ocr_all, ocr_band)
    print(f"[OK] OCR tokens merged: {len(ocr['text'])}")

    lines = extract_text_list(ocr, min_conf=MIN_CONF)
    print("\n--- Lines ---")
    for i, s in enumerate(lines, 1):
        print(f"{i:02d}: {s}")
        
    query = "PLACEHOLDER"

    boxes = find_text_boxes(ocr, query, case_sensitive=False, whole_word=False, min_conf=MIN_CONF)
    print(f"\nMatches for '{query}' ({len(query)} chars): {len(boxes)}")
    for i, (x, y, w, h) in enumerate(boxes, 1):
        print(f"  #{i}: x={x}, y={y}, w={w}, h={h}")
