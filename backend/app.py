import os
import uuid
import json

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from database import init_db, insert_analysis, get_analysis, list_analyses
from text_extraction import extract_text, clean_text
from nlp_engine import SimilarityEngine
from pdf_report import build_pdf

app = Flask(__name__, static_folder='dist', static_url_path='/')
CORS(app)

# Two files of up to 25 MB each.
app.config['MAX_CONTENT_LENGTH'] = 60 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
REPORT_FOLDER = os.path.join(BASE_DIR, 'reports')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt'}

engine = SimilarityEngine()
init_db()


def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'device': engine.device,
        'model_loaded': engine.model is not None,
    })


@app.route('/api/analyze', methods=['POST'])
def analyze():
    if 'file_a' not in request.files or 'file_b' not in request.files:
        return jsonify({'error': 'Both files are required.'}), 400

    file_a = request.files['file_a']
    file_b = request.files['file_b']

    if not file_a.filename or not file_b.filename:
        return jsonify({'error': 'Both files are required.'}), 400

    if not allowed_file(file_a.filename) or not allowed_file(file_b.filename):
        return jsonify({
            'error': 'Only PDF, DOCX and TXT files are supported (up to 25 MB each).'
        }), 400

    analysis_id = str(uuid.uuid4())
    folder = os.path.join(UPLOAD_FOLDER, analysis_id)
    os.makedirs(folder, exist_ok=True)

    path_a = os.path.join(folder, secure_filename(file_a.filename))
    path_b = os.path.join(folder, secure_filename(file_b.filename))
    file_a.save(path_a)
    file_b.save(path_b)

    try:
        text_a = clean_text(extract_text(path_a))
        text_b = clean_text(extract_text(path_b))
    except Exception as exc:  # noqa: BLE001
        return jsonify({'error': f'Failed to read uploaded files: {exc}'}), 422

    result = engine.analyze(text_a, text_b)
    result['document_a'] = {
        'name': file_a.filename,
        'sentences': len(result.get('sentences_a', [])),
    }
    result['document_b'] = {
        'name': file_b.filename,
        'sentences': len(result.get('sentences_b', [])),
    }

    result_json = json.dumps(result)
    insert_analysis(
        analysis_id, file_a.filename, file_b.filename,
        result['similarity_score'], result['label'], result_json,
    )

    return jsonify({
        'analysis_id': analysis_id,
        'similarity_score': result['similarity_score'],
        'label': result['label'],
        'counts': result['counts'],
        'coverage': result['coverage'],
        'matches': result['matches'],
        'passages': result['passages'],
    })


@app.route('/api/result/<analysis_id>', methods=['GET'])
def result(analysis_id):
    row = get_analysis(analysis_id)
    if not row:
        return jsonify({'error': 'Analysis not found.'}), 404

    result = json.loads(row['result_json'])
    result['analysis_id'] = analysis_id
    result['created_at'] = row['created_at']
    result['document_a'] = {'name': row['filename_a']}
    result['document_b'] = {'name': row['filename_b']}
    return jsonify(result)


@app.route('/api/result/<analysis_id>/json', methods=['GET'])
def export_json(analysis_id):
    row = get_analysis(analysis_id)
    if not row:
        return jsonify({'error': 'Analysis not found.'}), 404

    path = os.path.join(REPORT_FOLDER, f'{analysis_id}.json')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(row['result_json'])

    return send_file(
        path, mimetype='application/json', as_attachment=True,
        download_name=f'veritext-result-{analysis_id}.json',
    )


@app.route('/api/result/<analysis_id>/pdf', methods=['GET'])
def export_pdf(analysis_id):
    row = get_analysis(analysis_id)
    if not row:
        return jsonify({'error': 'Analysis not found.'}), 404

    result = json.loads(row['result_json'])
    result['analysis_id'] = analysis_id
    result['created_at'] = row['created_at']

    path = os.path.join(REPORT_FOLDER, f'{analysis_id}.pdf')
    build_pdf(path, result)

    return send_file(
        path, mimetype='application/pdf', as_attachment=True,
        download_name=f'veritext-report-{analysis_id}.pdf',
    )


@app.route('/api/history', methods=['GET'])
def history():
    return jsonify({'history': list_analyses()})


# Single-page application fallback: serve the built frontend, letting
# client-side routing handle pages such as /result/<id>.
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def spa(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
