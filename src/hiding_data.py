import cv2
import numpy as np
from detector import detector

def blackout_regions(output_path, categories, image_path=None):
    """
    Black out sensitive areas in an image.

    output_path: where to save the blacked-out image
    categories: a dictionary of categories and if they are sensitive
    image_path: path to original image if none is provided, a screenshot of the current screen will be taken
    """
    cat = [key for key in categories.keys() if categories[key] == 1]

    img, boxes = detector(cat, image_path)

    for (x, y, w, h) in boxes:
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 0), -1)

    cv2.imwrite(output_path, img)
    return output_path

def blur_regions(output_path, categories, image_path=None):
    """
    Blur sensitive areas in an image.

    output_path: where to save the blurred image
    categories: a dictionary of categories and if they are sensitive
    image_path: path to original image if none is provided, a screenshot of the current screen will be taken
    """
    cat = [key for key in categories.keys() if categories[key] == 1]
    
    img, boxes = detector(cat, image_path)

    for (x, y, w, h) in boxes:
        roi = img[y:y+h, x:x+w]
        blurred = cv2.GaussianBlur(roi, (51, 51), 0)
        img[y:y+h, x:x+w] = blurred

    cv2.imwrite(output_path, img)
    return output_path

if __name__ == "__main__":
    blur_regions("output_blurred.png", {})