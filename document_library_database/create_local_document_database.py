import os
import sqlite3

def create_local_document_database(db_path:str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            version TEXT,
            valid_from TEXT,
            valid_to TEXT,
            employer TEXT,
            title TEXT,
            notes TEXT,
            language TEXT,
            filetype TEXT,
            filename TEXT,
            file_size_bytes INTEGER,
            file_path TEXT,
            vectorstore_path TEXT,
            upload_date TEXT,
            chunk_size INTEGER,
            chunk_overlap INTEGER,
            embedding_model TEXT,
            processing_status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Collections table

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collections(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_by TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Junction table for many-to-many relationship between documents and collections
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_collections(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            collection_id INTEGER NOT NULL,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            added_by TEXT,
            FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE,
            FOREIGN KEY (collection_id) REFERENCES collections (id) ON DELETE CASCADE,
            UNIQUE(document_id, collection_id)
        )''')
        
        # Create indexes for better performance
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_documents_employer ON documents(employer)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_documents_upload_date ON documents(upload_date)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(name)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_document_collections_document_id ON document_collections(document_id)''')
    cursor.execute('''CREATE INDEX IF NOT EXISTS idx_document_collections_collection_id ON document_collections(collection_id)''')
        
    conn.commit()
    conn.close()