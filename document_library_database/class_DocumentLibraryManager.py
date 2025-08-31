
import sqlite3
from datetime import datetime

from document_library_database import ensure_document_library_db
from document_library_database.class_DocumentMetadataModel import DocumentMetadata
from document_library_database.documents.delete_documents import delete_document
from .class_DocumentsManager import DocumentsManager

class DocumentLibraryManager:
    """Singleton database operations manager for document library"""
    _instance = None
    _db_path = 'document_library_metadata.db'
    ensure_document_library_db(_db_path)
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DocumentLibraryManager, cls).__new__(cls)
            ensure_document_library_db(cls._db_path) 
            cls._instance.Documents = DocumentsManager()
        return cls._instance
    
    @classmethod
    def get_connection(cls):
        """Get database connection"""
        return sqlite3.connect(cls._db_path)
    
    @classmethod
    def set_db_path(cls, db_path):
        """Set database path (useful for testing)"""
        cls._db_path = db_path
        ensure_document_library_db()
    
    @classmethod
    def delete_document(cls, document_id, soft_delete=True):
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, vectorstore_path FROM documents WHERE id = ?', (document_id,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return False
            delete_document(
                connection=cls.get_connection(),
                cursor=cls.get_connection().cursor(),
                document_id=document_id,
                soft_delete=soft_delete
            )
    @classmethod
    def create_collection(cls, name, description=None, created_by=None):
        """Create a new collection"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO collections (name, description, created_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, description, created_by, datetime.now().isoformat(), datetime.now().isoformat()))
            collection_id = cursor.lastrowid
            conn.commit()
            return collection_id
        except sqlite3.IntegrityError:
            raise ValueError(f"Collection '{name}' already exists")
        finally:
            conn.close()
    
    @classmethod
    def get_all_collections(cls, include_inactive=False):
        """Get all collections with document counts"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        where_clause = "" if include_inactive else "WHERE c.is_active = 1"
        
        cursor.execute(f'''
            SELECT 
                c.id, 
                c.name, 
                c.description, 
                c.created_by, 
                c.is_active,
                c.created_at,
                c.updated_at,
                COUNT(dc.document_id) as document_count
            FROM collections c
            LEFT JOIN document_collections dc ON c.id = dc.collection_id
            {where_clause}
            GROUP BY c.id, c.name, c.description, c.created_by, c.is_active, c.created_at, c.updated_at
            ORDER BY c.created_at DESC
        ''')
        
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
                'document_count': row[7]
            })
        
        conn.close()
        return collections
    
    @classmethod
    def get_collection_by_id(cls, collection_id):
        """Get collection by ID"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, name, description, created_by, is_active, created_at, updated_at
            FROM collections 
            WHERE id = ?
        ''', (collection_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'created_by': row[3],
                'is_active': bool(row[4]),
                'created_at': row[5],
                'updated_at': row[6]
            }
        return None
    
    @classmethod
    def update_collection(cls, collection_id, name=None, description=None):
        """Update collection"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().isoformat())
            params.append(collection_id)
            
            cursor.execute(f'''
                UPDATE collections 
                SET {', '.join(updates)}
                WHERE id = ?
            ''', params)
            conn.commit()
        
        conn.close()
    
    @classmethod
    def delete_collection(cls, collection_id, soft_delete=True):
        """Delete collection (soft delete by default)"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        
        if soft_delete:
            cursor.execute('''
                UPDATE collections 
                SET is_active = 0, updated_at = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), collection_id))
        else:
            # Hard delete - will also delete document_collections due to CASCADE
            cursor.execute('DELETE FROM collections WHERE id = ?', (collection_id,))
        
        conn.commit()
        conn.close()
    
    # Document operations
    @classmethod
    def create_document(cls, 
                document_metadata: DocumentMetadata, 
                vectorstore_path: str,
                document_description: str=""):
        """Create a new document"""
        conn = cls.get_connection()
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
        #if there is a collection_id in document_metadata, associate the document with the appropriate collection
        document_id = cursor.lastrowid
        if document_metadata.collection_id:
            cursor.execute('''
                INSERT INTO document_collections (document_id, collection_id, added_at)
                VALUES (?, ?, ?)
            ''', (document_id, document_metadata.collection_id, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return document_id
    
    @classmethod
    def get_document_by_id(cls, document_id):
        """Get document by ID"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM documents WHERE id = ?', (document_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, row))
        return None
    
    @classmethod
    def get_documents_by_collection(cls, collection_id):
        """Get all documents in a collection"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT d.*, dc.added_at, dc.added_by
            FROM documents d
            JOIN document_collections dc ON d.id = dc.document_id
            WHERE dc.collection_id = ?
            ORDER BY dc.added_at DESC
        ''', (collection_id,))
        
        documents = []
        for row in cursor.fetchall():
            columns = [description[0] for description in cursor.description]
            documents.append(dict(zip(columns, row)))
        
        conn.close()
        return documents
    
    @classmethod
    def update_document_processing_status(cls, document_id, status):
        """Update document processing status"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE documents 
            SET processing_status = ?, updated_at = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), document_id))
        conn.commit()
        conn.close()
    
    # Document-Collection relationship operations
    @classmethod
    def add_document_to_collection(cls, document_id, collection_id, added_by=None):
        """Add document to collection"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO document_collections (document_id, collection_id, added_at, added_by)
                VALUES (?, ?, ?, ?)
            ''', (document_id, collection_id, datetime.now().isoformat(), added_by))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Document already in collection
            return False
        finally:
            conn.close()
    
    @classmethod
    def remove_document_from_collection(cls, document_id, collection_id):
        """Remove document from collection"""
        conn = cls.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM document_collections 
            WHERE document_id = ? AND collection_id = ?
        ''', (document_id, collection_id))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0
    
    @classmethod
    def get_collections_for_document(cls, document_id):
        """Get all collections containing a document"""
        conn = cls.get_connection()
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
    
    # Search and query operations
    @classmethod
    def search_documents(cls, query, collection_id=None):
        """Search documents by title, employer, or notes"""
        conn = cls.get_connection()
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