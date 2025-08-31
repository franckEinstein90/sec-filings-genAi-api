import sqlite3
import os
from .create_local_document_database import create_local_document_database

def ensure_document_library_db(db_path):
    if not os.path.exists(db_path):
        create_local_document_database(db_path)    


