from flask import Flask, request, jsonify, render_template, send_file
import os
import PyPDF2
from werkzeug.utils import secure_filename
import re
import pandas as pd
from datetime import datetime
import pytesseract as tess
from PIL import Image
import csv

app = Flask(__name__)

UPLOAD_FOLDER = os.path.abspath('uploads')
EXCEL_FOLDER = os.path.abspath('excel_output')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['EXCEL_FOLDER'] = EXCEL_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EXCEL_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def analyze_with_Regex(text_content):
    """Analyze text content using regex for specific patterns"""
    if isinstance(text_content, list):
        text_content = " ".join(text_content)
    
    # Advanced regex patterns based on the template provided
    patterns = {
        'invoice_number': r'Invoice Number:\s*(\w+)',
        'date': r'Date:\s*(\d{2}/\d{2}/\d{4})',
        'total_amount': r'Total Amount:\s*\$([\d,]+\.\d{2})|Total amount (.*)|TOTAL (.*)|Total (.*)',
        'billed_to': r'BILLED TO: (.*)|BILLED TO:\n.*\n(.*)|BILL TO:\n.*\n(.*) D',
        'billed_from': r'PAY TO: (.*)|FROM.*\n.*\n(.*)|Account Name: (.*)',
        'phone_number': r'\d{3}-\d{3}-\d{4}|\d{10}',
        'email': r'[a-z0-9A-Z_]*@[a-z0-9A-Z_]*\.com'
    }
    
    analysis_result = {}
    
    for key, pattern in patterns.items():
        matches = re.findall(pattern, text_content)
        if matches:
            if isinstance(matches[0], tuple):  # Handle groups in regex
                for group in matches[0]:
                    if group:
                        analysis_result[key] = group.strip()
                        break
            else:
                analysis_result[key] = matches[0].strip()
    
    return {
        'success': True,
        'analysis': analysis_result
    }

def extract_pdf_content(filepath):
    """Extract text content from PDF file"""
    text_content = []
    try:
        with open(filepath, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            num_pages = len(reader.pages)
            
            # Extract text from each page
            for page_num in range(num_pages):
                page = reader.pages[page_num]
                text = page.extract_text()
                if text is None:
                    text = "" 
                text_content.append(text)
            
            analysis_result = analyze_with_Regex(text_content)
            
            return {
                'success': True,
                'num_pages': num_pages,
                'content': text_content,
                'analysis': analysis_result['analysis']
            }
                
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def extract_image_content(filepath):
    """Extract text content from image file using OCR"""
    try:
        image = Image.open(filepath)
        text = tess.image_to_string(image)
        
        analysis_result = analyze_with_Regex(text)
        
        return {
            'success': True,
            'content': text,
            'analysis': analysis_result['analysis']
        }
                
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def save_to_excel(data, filename):
    """Save extracted data to Excel file"""
    try:
        # Convert dictionary to DataFrame
        df = pd.DataFrame([data])
        
        # Ensure directory exists
        os.makedirs(app.config['EXCEL_FOLDER'], exist_ok=True)
        
        # Create Excel file with absolute path
        excel_path = os.path.abspath(os.path.join(app.config['EXCEL_FOLDER'], filename))
        df.to_excel(excel_path, index=False)
        
        # Verify file was created
        if not os.path.isfile(excel_path):
            return {
                'success': False,
                'error': 'Failed to create Excel file'
            }
        
        return {
            'success': True,
            'path': excel_path
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def save_to_csv(data, filename):
    """Save extracted data to CSV file"""
    try:
        headers = ["COMPANY NAME", "CUSTOMER", "PHONE NUMBER", "EMAIL", "PAYMENT DUE"]
        
        # Map extracted data to CSV headers
        company = data.get('billed_from', 'NA')
        customer = data.get('billed_to', 'NA')
        phone = data.get('phone_number', 'NA')
        email = data.get('email', 'NA')
        payment = data.get('total_amount', 'NA')
        
        # Ensure directory exists
        os.makedirs(app.config['EXCEL_FOLDER'], exist_ok=True)
        
        # Create CSV with absolute path
        csv_path = os.path.abspath(os.path.join(app.config['EXCEL_FOLDER'], filename))
        
        # Write the CSV file
        with open(csv_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerows([headers, [company, customer, phone, email, payment]])
        
        # Verify file was created
        if not os.path.isfile(csv_path):
            return {
                'success': False,
                'error': 'Failed to create CSV file'
            }
            
        return {
            'success': True,
            'path': csv_path
        }
    except Exception as e:
        print(f"CSV creation error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Check if it's PDF or image
            file_extension = filename.rsplit('.', 1)[1].lower()
            
            if file_extension == 'pdf':
                # Extract content from PDF
                extracted_data = extract_pdf_content(filepath)
            else:
                # Extract content from image using OCR
                extracted_data = extract_image_content(filepath)
            
            if extracted_data['success']:
                # Generate filenames
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                excel_filename = f"invoice_data_{timestamp}.xlsx"
                csv_filename = f"invoice_data_{timestamp}.csv"
                
                # Save to Excel
                excel_result = save_to_excel(extracted_data['analysis'], excel_filename)
                
                # Save to CSV
                csv_result = save_to_csv(extracted_data['analysis'], csv_filename)
                
                # Clean up the uploaded file when done
                try:
                    os.remove(filepath)
                except:
                    pass  # If cleanup fails, just continue
                
                if excel_result['success'] and csv_result['success']:
                    return jsonify({
                        'success': True,
                        'data': extracted_data['analysis'],
                        'excel_file': excel_filename,
                        'csv_file': csv_filename
                    })
                else:
                    error_msg = ""
                    if not excel_result['success']:
                        error_msg += f"Excel error: {excel_result['error']}. "
                    if not csv_result['success']:
                        error_msg += f"CSV error: {csv_result['error']}"
                    
                    return jsonify({
                        'success': False,
                        'error': f"Failed to create output files: {error_msg}"
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': f"File uploaded but content extraction failed: {extracted_data['error']}"
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    else:
        return jsonify({'success': False, 'error': f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'})

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        # Make sure the directory exists
        os.makedirs(app.config['EXCEL_FOLDER'], exist_ok=True)
        
        # Get the absolute path
        path = os.path.abspath(os.path.join(app.config['EXCEL_FOLDER'], filename))
        
        # Check if file exists
        if not os.path.isfile(path):
            return jsonify({
                'success': False, 
                'error': f"File not found: {filename}. Please try processing your invoice again."
            })
            
        # Log the path being accessed (for debugging)
        print(f"Attempting to download file: {path}")
        
        # Send the file
        return send_file(path, as_attachment=True)
    except Exception as e:
        print(f"Download error: {str(e)}")
        return jsonify({'success': False, 'error': f"Download failed: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)