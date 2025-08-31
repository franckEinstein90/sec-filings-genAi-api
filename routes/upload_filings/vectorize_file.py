import os
from flask import Blueprint, request, jsonify
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

def vectorize_file(
        file, 
        vectorization_params, 
        openai_api_key):

    results={
        "chunks": 0,
        "processing_steps": []
    }

    if file.filename.lower().endswith('.pdf'):
        # Save the file temporarily
        temp_path = f"/tmp/{file.filename}"
        try:
            file.save(temp_path)
            embeddings = OpenAIEmbeddings(
                model=vectorization_params['embedding_model'], 
                openai_api_key=openai_api_key)
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=vectorization_params['chunk_size'], 
                chunk_overlap=vectorization_params['chunk_overlap'], 
                separators=["\n\n", "\n", " ", ""])
            loader = PyPDFLoader(temp_path)
            pages = loader.load()
            os.remove(temp_path)
            documents = splitter.split_documents(pages)   
            results["chunks"] = len(documents)
            results["processing_steps"].append(f"Created {len(documents)} text chunks")         
            vectorstore = FAISS.from_documents(documents, embeddings)
            vectorstore_path = f"vectorstore/{vectorization_params['vectorstore_name']}"
            vectorstore.save_local(vectorstore_path)
            results["vectorstore_path"] = vectorstore_path
            return results
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return {'error': str(e)}
    else:
        return {'error': 'Only PDF files are supported'}
