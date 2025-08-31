import os
from flask import Flask, jsonify
from document_library_database import ensure_document_library_db
from routes.upload_filings.process_upload import upload_cba_bp
from routes.query_collective_bargaining_agreement.query_collective_bargaining_agreement import query_cba_bp
from routes.collections.post_collections import collection_bp


app = Flask(__name__)
app.register_blueprint(upload_cba_bp)
app.register_blueprint(query_cba_bp)
app.register_blueprint(collection_bp)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})
    
@app.route('/agreements', methods=['GET'])
def list_agreements():
    vectorstore_dir = os.path.join(os.path.dirname(__file__), 'vectorstore')
    if not os.path.exists(vectorstore_dir):
        return jsonify({'agreements': []})

    agreements = [{
        "name":f,
        "collection":"test"
        } for f in os.listdir(vectorstore_dir) if os.path.isdir(os.path.join(vectorstore_dir, f))]
    return jsonify({'agreements': agreements})

if __name__ == '__main__':
    app.run(debug=True)
