from flask import Blueprint, request, jsonify

from document_library_database.class_DocumentLibraryManager import DocumentLibraryManager
from union_steward_mode import steward_rag_query

query_cba_bp = Blueprint('query_cba', __name__)

@query_cba_bp.route('/query_collective_bargaining_agreement', methods=['POST'])
def query_collective_bargaining_agreement():
    data = request.get_json()
    prompt = data.get('prompt')
    selected_document = data.get('document')
    try:
        document_db_record = DocumentLibraryManager.get_document_by_id(selected_document['id'])
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    vectorstore_path = document_db_record['vectorstore_path']
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    answer = steward_rag_query(
        query=prompt,
        vectorstore_path=vectorstore_path
    )
    
    results = {
        "answer": answer
    }
    return jsonify(results), 200
