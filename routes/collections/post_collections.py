from flask import Blueprint, request, jsonify
from document_library_database import DocumentLibraryManager

collection_bp = Blueprint('collections', __name__)

@collection_bp.route('/collections/create', methods=['POST'])
def create_collection():
    try:
        # Validate JSON payload exists
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        
        # Validate required fields
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'Collection name is required'}), 400
        
        # Optional fields with defaults
        description = data.get('description', '').strip()
        created_by = data.get('created_by')
        
        # Validate name length (optional but recommended)
        if len(name) > 255:
            return jsonify({'error': 'Collection name too long (max 255 characters)'}), 400
        
        # Create collection
        collection_id = DocumentLibraryManager.create_collection(
            name=name, 
            description=description or None,  # Convert empty string to None
            created_by=created_by
        )
        
        # Return created collection details
        collection = DocumentLibraryManager.get_collection_by_id(collection_id)
        
        return jsonify({
            'message': 'Collection created successfully',
            'collection': collection
        }), 201
        
    except ValueError as e:
        # Handle specific database constraint errors (e.g., duplicate names)
        return jsonify({'error': str(e)}), 409  # Conflict
    except Exception as e:
        # Log the error for debugging (in production, use proper logging)
        print(f"Error creating collection: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@collection_bp.route('/collections', methods=['GET'])
def list_collections():
    """Get all collections"""
    try:
        include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
        collections = DocumentLibraryManager.get_all_collections(include_inactive=include_inactive)
        
        return jsonify({
            'collections': collections,
            'count': len(collections)
        }), 200
        
    except Exception as e:
        print(f"Error fetching collections: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@collection_bp.route('/collections/<int:collection_id>', methods=['GET'])
def get_collection(collection_id):
    """Get a specific collection"""
    try:
        collection = DocumentLibraryManager.get_collection_by_id(collection_id)
        
        if not collection:
            return jsonify({'error': 'Collection not found'}), 404
        
        # Optionally include documents in the collection
        include_documents = request.args.get('include_documents', 'false').lower() == 'true'
        if include_documents:
            documents = DocumentLibraryManager.get_documents_by_collection(collection_id)
            collection['documents'] = documents
        
        return jsonify({'collection': collection}), 200
        
    except Exception as e:
        print(f"Error fetching collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@collection_bp.route('/collections/<int:collection_id>/update', methods=['PUT', 'POST'])
def update_collection(collection_id):
    """Update a collection"""
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        
        # Check if collection exists
        existing_collection = DocumentLibraryManager.get_collection_by_id(collection_id)
        if not existing_collection:
            return jsonify({'error': 'Collection not found'}), 404
        
        # Get update fields
        name = data.get('name', '').strip() if 'name' in data else None
        description = data.get('description', '').strip() if 'description' in data else None
        
        # Validate name if provided
        if name is not None:
            if not name:
                return jsonify({'error': 'Collection name cannot be empty'}), 400
            if len(name) > 255:
                return jsonify({'error': 'Collection name too long (max 255 characters)'}), 400
        
        # Update collection
        DocumentLibraryManager.update_collection(
            collection_id=collection_id,
            name=name,
            description=description
        )
        
        # Return updated collection
        updated_collection = DocumentLibraryManager.get_collection_by_id(collection_id)
        
        return jsonify({
            'message': 'Collection updated successfully',
            'collection': updated_collection
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 409
    except Exception as e:
        print(f"Error updating collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@collection_bp.route('/collections/<int:collection_id>/delete', methods=['DELETE', 'POST'])
def delete_collection(collection_id):
    """Delete a collection"""
    try:
        # Check if collection exists
        existing_collection = DocumentLibraryManager.get_collection_by_id(collection_id)
        if not existing_collection:
            return jsonify({'error': 'Collection not found'}), 404
        
        # Get soft delete parameter
        hard_delete = request.args.get('hard_delete', 'false').lower() == 'true'
        
        # Delete collection
        DocumentLibraryManager.delete_collection(
            collection_id=collection_id,
            soft_delete=not hard_delete
        )
        
        return jsonify({
            'message': f'Collection {"permanently deleted" if hard_delete else "deactivated"} successfully'
        }), 200
        
    except Exception as e:
        print(f"Error deleting collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@collection_bp.route('/collections/<int:collection_id>/documents/add', methods=['POST'])
def add_document_to_collection(collection_id):
    """Add a document to a collection"""
    try:
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        
        data = request.get_json()
        document_id = data.get('document_id')
        added_by = data.get('added_by')
        
        if not document_id:
            return jsonify({'error': 'document_id is required'}), 400
        
        # Check if collection exists
        collection = DocumentLibraryManager.get_collection_by_id(collection_id)
        if not collection:
            return jsonify({'error': 'Collection not found'}), 404
        
        # Check if document exists
        document = DocumentLibraryManager.get_document_by_id(document_id)
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        # Add document to collection
        success = DocumentLibraryManager.add_document_to_collection(
            document_id=document_id,
            collection_id=collection_id,
            added_by=added_by
        )
        
        if success:
            return jsonify({
                'message': 'Document added to collection successfully'
            }), 201
        else:
            return jsonify({
                'error': 'Document is already in this collection'
            }), 409
        
    except Exception as e:
        print(f"Error adding document to collection: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@collection_bp.route('/collections/<int:collection_id>/documents/<int:document_id>/remove', methods=['DELETE', 'POST'])
def remove_document_from_collection(collection_id, document_id):
    """Remove a document from a collection"""
    try:
        success = DocumentLibraryManager.remove_document_from_collection(
            document_id=document_id,
            collection_id=collection_id
        )
        
        if success:
            return jsonify({
                'message': 'Document removed from collection successfully'
            }), 200
        else:
            return jsonify({
                'error': 'Document not found in this collection'
            }), 404
        
    except Exception as e:
        print(f"Error removing document from collection: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@collection_bp.route('/collections/<int:collection_id>/documents', methods=['GET'])
def get_collection_documents(collection_id):
    """Get all documents in a collection"""
    try:
        # Check if collection exists
        collection = DocumentLibraryManager.get_collection_by_id(collection_id)
        if not collection:
            return jsonify({'error': 'Collection not found'}), 404
        
        documents = DocumentLibraryManager.get_documents_by_collection(collection_id)
        
        return jsonify({
            'collection_id': collection_id,
            'collection_name': collection['name'],
            'documents': documents,
            'count': len(documents)
        }), 200
        
    except Exception as e:
        print(f"Error fetching documents for collection {collection_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Error handlers for the blueprint
@collection_bp.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@collection_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405