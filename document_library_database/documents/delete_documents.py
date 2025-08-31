import datetime

def delete_document(
        connection,
        cursor, 
        document_id, soft_delete=True):
    """
    Delete document (soft delete by default)
    """
    cursor = connection.cursor()

    # First, check if document exists
    cursor.execute('SELECT id FROM documents WHERE id = ?', (document_id,))
    if not cursor.fetchone():
        connection.close()
        return False
    
    if soft_delete:
        # Soft delete - mark as inactive/deleted but keep record
        cursor.execute('''
            UPDATE documents 
            SET processing_status = 'deleted', updated_at = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), document_id))
    else:
        # Hard delete - remove document and all collection associations
        # First remove from all collections
        cursor.execute('DELETE FROM document_collections WHERE document_id = ?', (document_id,))
        # Then delete the document record
        cursor.execute('DELETE FROM documents WHERE id = ?', (document_id,))
    
    rows_affected = cursor.rowcount
    connection.commit()
    connection.close()
    return rows_affected > 0
