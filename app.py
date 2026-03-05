from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS
import os
import json

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/path/to/upload')
ALLOW_PUBLIC_READ = os.getenv('ALLOW_PUBLIC_READ', 'false').lower() == 'true'

@app.route('/upload', methods=['POST'])
def upload_file():
    files = request.files.getlist('files')
    for file in files:
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    return jsonify({'message': 'Files uploaded successfully'}), 201

@app.route('/files/<path:filename>', methods=['GET'])
def get_file(filename):
    if ALLOW_PUBLIC_READ:
        return send_from_directory(UPLOAD_FOLDER, filename)
    return jsonify({'error': 'Unauthorized access'}), 403

@app.route('/api/list/<path:dir_path>', methods=['GET'])
def list_files(dir_path):
    full_path = os.path.join(UPLOAD_FOLDER, dir_path)
    if os.path.isdir(full_path):
        files = os.listdir(full_path)
        return jsonify(files), 200
    return jsonify({'error': 'Directory not found'}), 404

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)