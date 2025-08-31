from flask import Blueprint, request, jsonify
from document_library_database import DocumentMetadata, DocumentLibraryManager
from union_steward_mode import steward_rag_query
from .vectorize_file import vectorize_file

import os
import json

upload_cba_bp = Blueprint('documents', __name__)
@upload_cba_bp.route('/documents/upload', methods=['POST'])
def upload_document():
    results={
        "chunks": 0,
        "processing_steps": []
    }  
    doc_metadata = DocumentMetadata.from_flask_request(request)
    file = request.files.get('file')
    
    vectorstore_name = doc_metadata.file_name.rsplit('.', 1)[0]
    vectorization_params = json.loads(request.form.get('vectorization_params')) if request.form.get('vectorization_params') else {}
    vectorization_params['vectorstore_name'] = vectorstore_name

    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not file:
        return jsonify({'error': 'No file uploaded'}), 400
    try:
        results = vectorize_file(file, vectorization_params, openai_api_key)
        vectorstore_path = results.get('vectorstore_path')
        file_description = steward_rag_query(
            query="Provide a description of what this document is and what it does in less than 200 words. Who are the parties concerned? In the description, include the period of time it covers, when it begins application and when it ends if applicable",
            vectorstore_path=vectorstore_path
        )
        file_description = file_description['content']
        results['description'] = file_description
        document_id = DocumentLibraryManager.create_document(
            document_metadata=doc_metadata,
            document_description=file_description,
            vectorstore_path=vectorstore_path
        )
        results['document_id'] = document_id
        return jsonify({
            'message': 'File uploaded and vectorized successfully',
            'results': results
        }), 200 
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@upload_cba_bp.route('/documents', methods=['GET'])
def list_documents():

    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        collections = DocumentLibraryManager.get_all_collections(include_inactive=include_inactive)
        #for each collection, rollup all the contained documents into an object 
        #where the keys are the collection names
        rolled_up_documents = {}
        for collection in collections:
            documents = DocumentLibraryManager.get_documents_by_collection(collection['id'])
            rolled_up_documents[collection['name']] = documents

        return jsonify(rolled_up_documents), 200
        
    except Exception as e:
        print(f"Error fetching documents: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500
    
@upload_cba_bp.route('/documents/<int:document_id>', methods=['DELETE'])
def delete_document(document_id):
    try:
        DocumentLibraryManager.delete_document(document_id)
        return jsonify({'message': 'Document deleted successfully'}), 200
    except Exception as e:
        print(f"Error deleting document: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500