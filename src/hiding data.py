import cv2

# Blacking out sensitive regions
def blackout_regions(image_path, boxes, output_path):
    """
    Black out sensitive areas in an image.

    image_path: path to original image
    boxes: list of (x, y, w, h) coordinates for sensitive regions
    output_path: where to save the blacked-out image
    """
    img = cv2.imread(image_path)

    for (x, y, w, h) in boxes:
        # Draw a solid black rectangle over the sensitive region
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 0), -1)

    cv2.imwrite(output_path, img)
    return output_path


# Example usage:
sensitive_boxes = [
    (120, 200, 150, 40),  # box 1
    (300, 500, 200, 50)   # box 2
]

blackout_regions("input.png", sensitive_boxes, "output_blacked.png")

# Blur sensitive regions instead of blacking them out
def blur_regions(image_path, boxes, output_path):
    img = cv2.imread(image_path)

    for (x, y, w, h) in boxes:
        roi = img[y:y+h, x:x+w]
        blurred = cv2.GaussianBlur(roi, (51, 51), 0)
        img[y:y+h, x:x+w] = blurred

    cv2.imwrite(output_path, img)
    return output_path
