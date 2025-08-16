from google import genai
from ocr import *

client = genai.Client(api_key="AIzaSyDB8440WGk3uSMDriAi7PXs5zBIbfa-SYs")

response = client.models.generate_content(
    model="gemini-2.5-flash", contents="Explain how AI works in a few words"
)
print(response.text)

def detector(categories, image_path=None):

    img = capture_screen(image_path=image_path)
    cv2.imwrite("temp.png", img)
    
    H, W = img.shape[:2]

    ocr_all = run_ocr(img, psm=11)

    band_h = int(H * BOTTOM_BAND)
    roi = (0, H - band_h, W, band_h)
    
    
    ocr_band = run_ocr(
        img, psm=7,
        whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",
        roi=roi
    )


    ocr = merge_ocr_dicts(ocr_all, ocr_band)

    lines = extract_text_list(ocr, min_conf=MIN_CONF)
    
    
    response = client.models.generate_content(
        model="gemini-2.5-flash", 
        contents="You are to read a list of text, and identify any text that might be considered sensitive information, such as API keys, personal data, or confidential information. You are to only return the pieces of text that are considered sensitive information, seperated by commas. If the following list is empty, flag all sensitive data, if it is not empty, only flag the following:" + str(categories) +  ". \n Here is the list of lines:" + str(lines)
    )
    sensitive_info = []

    img = cv2.imread("temp.png")

    if not response.text:
        print("No response.")
        return img, []

    for line in response.text.split(","):
        line = line.strip()
        sensitive_info.extend(find_text_boxes(ocr, line, case_sensitive=False, whole_word=False, min_conf=MIN_CONF))

    for i, (x, y, w, h) in enumerate(sensitive_info):
        sensitive_info[i] = (int(x/1.9), int(y/1.9), int(w/1.9), int(h/1.9))

    print(sensitive_info)
    return img, sensitive_info

if __name__ == "__main__":
    detector()