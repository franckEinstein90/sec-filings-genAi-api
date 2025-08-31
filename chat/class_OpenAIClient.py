
# app/rag.py
import os
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError, RateLimitError, APITimeoutError, APIConnectionError

class RAGError(Exception):
    """Custom exception for RAG-related errors"""
    pass

class OpenAIClient:
    """Singleton OpenAI client to avoid recreating connections"""
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def get_client(self) -> OpenAI:
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RAGError("OPENAI_API_KEY is not set in environment variables")
            self._client = OpenAI(api_key=api_key)
        return self._client