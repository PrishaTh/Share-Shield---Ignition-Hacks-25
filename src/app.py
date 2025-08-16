from flask import Flask, request, jsonify
from flask_cors import CORS
import base64
import io
import cv2
import numpy as np
from PIL import Image
import tempfile
import os
import sys

# Add current directory to Python path to help with imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from detector import detector
    print("✓ Successfully imported detector module")
except ImportError as e:
    print(f"✗ Error importing detector: {e}")
    print("Make sure detector.py is in the same directory as app.py")
    sys.exit(1)

try:
    from hiding_data import blackout_regions, blur_regions
    print("✓ Successfully imported hiding_data module")
except ImportError as e:
    print(f"✗ Error importing hiding_data: {e}")
    print("Make sure hiding_data.py (not 'hiding data.py') is in the same directory")
    print("Rename 'hiding data.py' to 'hiding_data.py' if needed")
    sys.exit(1)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def convert_base64_to_image(base64_string):
    """Convert base64 string to OpenCV image"""
    # Remove data URL prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    # Decode base64
    image_data = base64.b64decode(base64_string)
    image = Image.open(io.BytesIO(image_data))
    
    # Convert PIL to OpenCV format
    opencv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return opencv_image

def save_temp_image(opencv_image):
    """Save OpenCV image to temporary file and return path"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    cv2.imwrite(temp_file.name, opencv_image)
    return temp_file.name

def format_findings(sensitive_info, img_shape):
    """Convert detector output to frontend format"""
    findings = []
    
    for i, (x, y, w, h) in enumerate(sensitive_info):
        findings.append({
            'id': str(i + 1),
            'label': 'sensitive_data',  # Your detector returns coordinates, so we use generic label
            'confidence': 0.9,  # Default confidence since your detector doesn't return this
            'bbox': [int(x), int(y), int(w), int(h)],
            'risk': 'high'  # Default to high risk for all detected items
        })
    
    return findings

@app.route('/api/scan-image', methods=['POST'])
def scan_image():
    try:
        data = request.get_json()
        
        if 'image' not in data:
            return jsonify({'error': 'No image data provided'}), 400
        
        # Convert base64 to OpenCV image
        opencv_image = convert_base64_to_image(data['image'])
        
        # Save to temporary file for detector
        temp_path = save_temp_image(opencv_image)
        
        try:
            # Run detection using your existing detector
            # Pass empty list to detect ALL sensitive information
            print(f"Running detection on: {temp_path}")
            img, sensitive_info = detector([], temp_path)  # Fixed: pass categories parameter
            print(f"Detection found {len(sensitive_info)} sensitive items")
            print(f"Sensitive info coordinates: {sensitive_info}")
            
            # Format findings for frontend
            findings = format_findings(sensitive_info, img.shape)
            
            return jsonify({'findings': findings})
            
        except PermissionError as pe:
            print(f"Permission error in scan_image: {str(pe)}")
            # Return empty findings instead of failing
            return jsonify({'findings': [], 'warning': 'API permission issue - detection skipped'})
            
        except Exception as detection_error:
            print(f"Detection error in scan_image: {str(detection_error)}")
            # Return empty findings instead of failing
            return jsonify({'findings': [], 'warning': f'Detection failed: {str(detection_error)}'})
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass  # Ignore cleanup errors
            
    except Exception as e:
        print(f"Error in scan_image: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan-frame', methods=['POST'])
def scan_frame():
    """Endpoint for real-time frame scanning"""
    try:
        data = request.get_json()
        
        if 'frameData' not in data:
            return jsonify({'error': 'No frame data provided'}), 400
        
        # Convert base64 to OpenCV image
        opencv_image = convert_base64_to_image(data['frameData'])
        
        # Save to temporary file for detector
        temp_path = save_temp_image(opencv_image)
        
        try:
            # Run detection using your existing detector
            # Pass empty list to detect ALL sensitive information
            img, sensitive_info = detector([], temp_path)  # Fixed: pass categories parameter
            
            # Format findings for frontend
            findings = format_findings(sensitive_info, img.shape)
            
            return jsonify({'findings': findings})
            
        except PermissionError as pe:
            print(f"Permission error in scan_frame: {str(pe)}")
            # Return empty findings instead of failing
            return jsonify({'findings': [], 'warning': 'API permission issue - detection skipped'})
            
        except Exception as detection_error:
            print(f"Detection error in scan_frame: {str(detection_error)}")
            # Return empty findings instead of failing
            return jsonify({'findings': [], 'warning': f'Detection failed: {str(detection_error)}'})
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass  # Ignore cleanup errors
            
    except Exception as e:
        print(f"Error in scan_frame: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/redact-image', methods=['POST'])
def redact_image():
    """Apply redaction to image and return redacted version"""
    try:
        data = request.get_json()
        
        if 'image' not in data:
            return jsonify({'error': 'No image data provided'}), 400
        
        # Convert base64 to OpenCV image
        opencv_image = convert_base64_to_image(data['image'])
        
        # Save to temporary file
        temp_input = save_temp_image(opencv_image)
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.png').name
        
        try:
            # Apply redaction based on method using your existing functions
            redaction_method = data.get('method', 'blackout')
            
            # Create empty categories dict to trigger detection of ALL sensitive info
            categories = {}
            
            try:
                if redaction_method == 'blur':
                    output_path = blur_regions(temp_output, categories, temp_input)
                else:
                    output_path = blackout_regions(temp_output, categories, temp_input)

                # Read the redacted image and convert back to base64
                redacted_image = cv2.imread(output_path)
                if redacted_image is None:
                    # If the output file doesn't exist, use the input image
                    redacted_image = opencv_image
                
            except (PermissionError, Exception) as redact_error:
                print(f"Redaction failed: {str(redact_error)}")
                # Return original image if redaction fails
                redacted_image = opencv_image
            
            _, buffer = cv2.imencode('.png', redacted_image)
            redacted_base64 = base64.b64encode(buffer).decode('utf-8')
            
            return jsonify({
                'redactedImage': f'data:image/png;base64,{redacted_base64}'
            })
            
        finally:
            # Clean up temporary files
            for path in [temp_input, temp_output]:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass  # Ignore cleanup errors
            
    except Exception as e:
        print(f"Error in redact_image: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'ScreenGuard API is running'})

if __name__ == '__main__':
    print("=" * 50)
    print("Starting ScreenGuard API server...")
    print("=" * 50)
    
    # Check if all required files exist
    required_files = ['detector.py', 'hiding_data.py', 'ocr.py']
    for file in required_files:
        if os.path.exists(file):
            print(f"✓ Found: {file}")
        else:
            print(f"✗ Missing: {file}")
    
    print("\nMake sure to install required packages:")
    print("pip install flask flask-cors opencv-python pillow numpy")
    print("Also ensure Tesseract OCR is installed and your Gemini API key is set in detector.py")
    print("\nServer starting on http://localhost:5000")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)