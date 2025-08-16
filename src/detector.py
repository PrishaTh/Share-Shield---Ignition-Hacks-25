from google import genai
from ocr import *

client = genai.Client(api_key="AIzaSyDB8440WGk3uSMDriAi7PXs5zBIbfa-SYs")

response = client.models.generate_content(
    model="gemini-2.5-flash", contents="Explain how AI works in a few words"
)
print(response.text)

def detector():
    
    img = capture_screen(monitor_index=1)
    H, W = img.shape[:2]
    # print(f"[OK] Captured screen: {W}x{H}")

    ocr_all = run_ocr(img, psm=11)

    band_h = int(H * BOTTOM_BAND)
    roi = (0, H - band_h, W, band_h)
    
    
    ocr_band = run_ocr(
        img, psm=7,
        whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",
        roi=roi
    )


    ocr = merge_ocr_dicts(ocr_all, ocr_band)
    # print(f"[OK] OCR tokens merged: {len(ocr['text'])}")

    lines = extract_text_list(ocr, min_conf=MIN_CONF)
    
    
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents="You are to read a list of text, and identify any text that might be considered sensitive information, such as API keys, personal data, or confidential information. You are to only return the pieces of text that are considered sensitive information, seperated by commas. Here is the list of lines:" + str(lines)
    )
    sensitive_info = []

    for line in response.text.split(","):
        line = line.strip()
        sensitive_info.extend(find_text_boxes(ocr, line, case_sensitive=False, whole_word=False, min_conf=MIN_CONF))

    print(sensitive_info)
    return sensitive_info

if __name__ == "__main__":
    detector()