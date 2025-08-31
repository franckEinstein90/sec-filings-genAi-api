
import sqlite3
from datetime import datetime
from document_library_database.class_DocumentMetadataModel import DocumentMetadata

class DocumentsManager:
    """Singleton manager for document operations"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DocumentsManager, cls).__new__(cls)
        return cls._instance
    
    def _get_connection(self):
        """Get database connection from main manager"""
        from .class_DocumentLibraryManager import DocumentLibraryManager
        return DocumentLibraryManager.get_connection()
    
    def create(self, document_metadata: DocumentMetadata, vectorstore_path: str, document_description: str = ""):
        """Create a new document"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO documents (
                filetype, filename, vectorstore_path, upload_date, description
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            document_metadata.file_type, 
            document_metadata.file_name, 
            vectorstore_path,
            datetime.now().isoformat(),
            document_description
        ))
        # If there is a collection_id in document_metadata, associate the document with the appropriate collection
        document_id = cursor.lastrowid
        if document_metadata.collection_id:
            cursor.execute('''
                INSERT INTO document_collections (document_id, collection_id, added_at)
                VALUES (?, ?, ?)
            ''', (document_id, document_metadata.collection_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return document_id
    
    def get_by_id(self, document_id):
        """Get document by ID"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documents WHERE id = ?', (document_id,))
        
        row = cursor.fetchone()
        if row:
            columns = [description[0] for description in cursor.description]
            result = dict(zip(columns, row))
        else:
            result = None
        
        conn.close()
        return result
    
    def update_processing_status(self, document_id, status):
        """Update document processing status"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE documents 
            SET processing_status = ?, updated_at = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), document_id))
        conn.commit()
        conn.close()
    
    def get_collections(self, document_id):
        """Get all collections containing a document"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, dc.added_at, dc.added_by
            FROM collections c
            JOIN document_collections dc ON c.id = dc.collection_id
            WHERE dc.document_id = ? AND c.is_active = 1
            ORDER BY dc.added_at DESC
        ''', (document_id,))
        
        collections = []
        for row in cursor.fetchall():
            collections.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'created_by': row[3],
                'is_active': bool(row[4]),
                'created_at': row[5],
                'updated_at': row[6],
                'added_at': row[7],
                'added_by': row[8]
            })
        
        conn.close()
        return collections
    
    def search(self, query, collection_id=None):
        """Search documents by title, employer, or notes"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        base_query = '''
            SELECT DISTINCT d.*
            FROM documents d
        '''
        
        conditions = []
        params = []
        
        if collection_id:
            base_query += ' JOIN document_collections dc ON d.id = dc.document_id'
            conditions.append('dc.collection_id = ?')
            params.append(collection_id)
        
        if query:
            search_condition = '''
                (d.title LIKE ? OR d.employer LIKE ? OR d.notes LIKE ?)
            '''
            conditions.append(search_condition)
            search_param = f'%{query}%'
            params.extend([search_param, search_param, search_param])
        
        if conditions:
            base_query += ' WHERE ' + ' AND '.join(conditions)
        
        base_query += ' ORDER BY d.created_at DESC'
        
        cursor.execute(base_query, params)
        
        documents = []
        for row in cursor.fetchall():
            columns = [description[0] for description in cursor.description]
            documents.append(dict(zip(columns, row)))
        
        conn.close()
        return documents