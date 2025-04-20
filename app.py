from flask import Flask, request, jsonify, render_template
import os
import PyPDF2
from werkzeug.utils import secure_filename
import re

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def analyze_with_Regex(text_content):
    """Analyze text content using regex for specific patterns"""    
    # Example regex patterns for analysis
    patterns = {
        'invoice_number': r'Invoice Number:\s*(\w+)',
        'date': r'Date:\s*(\d{2}/\d{2}/\d{4})',
        'total_amount': r'Total Amount:\s*\$([\d,]+\.\d{2})',
        'billed_to': r'Billed To:\s*([\w\s,]+)',
        'billed_from': r'Billed From:\s*([\w\s,]+)'
    }
    
    analysis_result = {}
    
    for key, pattern in patterns.items():
        matches = re.findall(pattern, " ".join(text_content))
        if matches:
            analysis_result[key] = matches
    
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
            
            if analysis_result['success']:
                return {
                    'success': True
                }
            else:
                return {
                    'success': True,
                    'num_pages': num_pages,
                    'content': text_content,
                    'analysis': f"Analysis failed: {analysis_result['error']}"
                }
                
    except Exception as e:
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
            
            file_size = os.path.getsize(filepath)
            
            # Extract content from PDF
            pdf_data = extract_pdf_content(filepath)
            
            if pdf_data['success']:
                content = [str(text) for text in pdf_data['content']]
                
                return jsonify({
                    'success': True
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f"File uploaded but content extraction failed: {pdf_data['error']}"
                })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    else:
        return jsonify({'success': False, 'error': 'Invalid file type. Only PDF files are allowed.'})

if __name__ == '__main__':
    app.run(debug=True)
