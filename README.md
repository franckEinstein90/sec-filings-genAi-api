# 📄 SEC Filings GenAI API

Flask back-end API for ingesting and vectorizing SEC filings (10-K, 10-Q, 8-K, etc.), storing embeddings in a vector database, and exposing endpoints for retrieval-augmented generation (RAG) queries on financial documents.  

This project is the **back-end** of the SEC Filings GenAI solution. The companion front-end lives in [sec-filings-genAi-app](https://github.com/YOUR_USERNAME/sec-filings-genAi-app).

---

## ✨ Features

- 📥 **Ingest SEC Filings** (e.g., 10-K, 10-Q, 8-K) directly from EDGAR
- 🔍 **Vectorize and index filings** using SentenceTransformers + FAISS
- 🤖 **Semantic search endpoints** to query filings for financial and risk information
- 🧩 Modular design for swapping out vector store or embedding model
- 🧪 Basic test suite and GitHub Actions CI

