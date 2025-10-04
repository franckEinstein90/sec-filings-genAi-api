import os
from flask import Flask, jsonify
from src.routes import documents_bp
from src.routes import portfolio_bp

app = Flask(__name__)
app.register_blueprint(documents_bp, url_prefix="/api/v1/documents")
app.register_blueprint(portfolio_bp, url_prefix="/api/v1/portfolio")

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
