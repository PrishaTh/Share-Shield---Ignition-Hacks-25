from google import genai
from ocr import *
import os

client = genai.Client(api_key="AIzaSyDB8440WGk3uSMDriAi7PXs5zBIbfa-SYs")

# Test the client
try:
    response = client.models.generate_content(
        model="gemini-2.5-flash", contents="Explain how AI works in a few words"
    )
    print("✓ Gemini API connection successful")
    print(f"Test response: {response.text}")
except Exception as e:
    print(f"✗ Gemini API connection failed: {e}")

def detector(categories, image_path=None):
    """
    Detect sensitive information in an image.
    
    Args:
        categories: List of specific categories to detect. If empty, detects all.
        image_path: Path to image file. If None, captures screen.
    
    Returns:
        tuple: (image, list of bounding boxes)
    """
    try:
        # Capture or load the image
        img = capture_screen(image_path=image_path)
        temp_file = "temp.png"
        cv2.imwrite(temp_file, img)
        
        H, W = img.shape[:2]
        print(f"Image dimensions: {W}x{H}")

        # Run OCR on the full image
        ocr_all = run_ocr(img, psm=11)

        # Run OCR on bottom band for better detection of status bars, etc.
        band_h = int(H * BOTTOM_BAND)
        roi = (0, H - band_h, W, band_h)
        
        ocr_band = run_ocr(
            img, psm=7,
            whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-",
            roi=roi
        )

        # Merge OCR results
        ocr = merge_ocr_dicts(ocr_all, ocr_band)

        # Extract text lines from OCR results
        lines = extract_text_list(ocr, min_conf=MIN_CONF)
        print(f"Extracted {len(lines)} text lines from image")
        print(f"Sample lines: {lines[:3]}")  # Show first 3 lines for debugging
        
        # If no text found, return early
        if not lines:
            print("No text found in image")
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return img, []
        
        # Prepare prompt for Gemini
        if not categories or len(categories) == 0:
            category_instruction = "flag all sensitive data such as API keys, passwords, usernames, email addresses, phone numbers, credit card numbers, SSNs, addresses, and any other personally identifiable or confidential information"
        else:
            category_instruction = f"only flag the following categories: {', '.join(categories)}"
        
        prompt = f"""You are analyzing text extracted from an image to identify sensitive information. 

Instructions:
- {category_instruction}
- Only return the exact text pieces that are sensitive, separated by commas
- Do not include explanations or additional text
- If no sensitive information is found, return "NONE"

Text to analyze:
{chr(10).join(lines)}"""

        print(f"Sending prompt to Gemini with {len(lines)} lines of text")
        
        sensitive_info = []
        
        try:
            # Send to Gemini for analysis
            response = client.models.generate_content(
                model="gemini-2.5-flash", 
                contents=prompt
            )
            
            if not response.text or response.text.strip().upper() == "NONE":
                print("No sensitive information detected by Gemini")
            else:
                print(f"Gemini response: {response.text}")
                
                # Process each sensitive item found by Gemini
                sensitive_items = [item.strip() for item in response.text.split(",") if item.strip()]
                print(f"Processing {len(sensitive_items)} sensitive items")
                
                for item in sensitive_items:
                    if not item or item.upper() == "NONE":
                        continue
                        
                    # Find bounding boxes for this sensitive text
                    boxes = find_text_boxes(ocr, item, case_sensitive=False, whole_word=False, min_conf=MIN_CONF)
                    print(f"Found {len(boxes)} boxes for item: '{item}'")
                    
                    for box in boxes:
                        # Apply scaling correction (your OCR upscales by 1.9)
                        x, y, w, h = box
                        scaled_box = (int(x/1.9), int(y/1.9), int(w/1.9), int(h/1.9))
                        sensitive_info.append(scaled_box)
        
        except Exception as api_error:
            print(f"Gemini API error: {api_error}")
            # Fall back to basic regex detection if API fails
            sensitive_info = fallback_detection(ocr, lines)
        
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)

        print(f"Final sensitive info boxes: {sensitive_info}")
        return img, sensitive_info

    except Exception as e:
        print(f"Error in detector: {e}")
        import traceback
        traceback.print_exc()
        
        # Clean up temp file if it exists
        if 'temp_file' in locals() and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
        
        # Return empty results on error
        try:
            img = capture_screen(image_path=image_path)
            return img, []
        except:
            return np.zeros((100, 100, 3), dtype=np.uint8), []

def fallback_detection(ocr, lines):
    """
    Simple regex-based fallback detection when API fails
    """
    import re
    
    print("Using fallback detection...")
    sensitive_patterns = [
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'email'),
        (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', 'credit_card'),
        (r'\b\d{3}-\d{2}-\d{4}\b', 'ssn'),
        (r'\b(?:\+1-?)?\d{3}-?\d{3}-?\d{4}\b', 'phone'),
        (r'\b[A-Z0-9]{20,}\b', 'api_key'),
        (r'password\s*[:=]\s*\S+', 'password'),
        (r'key\s*[:=]\s*[A-Za-z0-9+/]{20,}', 'api_key'),
    ]
    
    sensitive_info = []
    text_all = ' '.join(lines)
    
    for pattern, category in sensitive_patterns:
        matches = re.finditer(pattern, text_all, re.IGNORECASE)
        for match in matches:
            matched_text = match.group()
            print(f"Fallback found {category}: {matched_text[:10]}...")
            
            # Find bounding boxes for this text
            boxes = find_text_boxes(ocr, matched_text, case_sensitive=False, whole_word=False, min_conf=MIN_CONF)
            for box in boxes:
                x, y, w, h = box
                scaled_box = (int(x/1.9), int(y/1.9), int(w/1.9), int(h/1.9))
                sensitive_info.append(scaled_box)
    
    print(f"Fallback detection found {len(sensitive_info)} items")
    return sensitive_info

if __name__ == "__main__":
    # Test the detector
    img, boxes = detector([])
    print(f"Detector test completed. Found {len(boxes)} sensitive regions.")