import os
from langchain_huggingface import HuggingFaceEmbeddings
from chromadb.config import Settings
import chromadb

# Constants
TPS_DB_PATH = "tps_knowledge_db"
CODEBASE_DB_PATH = "codebase_knowledge_db"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

class RAGUtils:
    _embedding_model = None

    @classmethod
    def get_embedding_model(cls):
        """
        Returns the shared embedding model instance.
        """
        if cls._embedding_model is None:
            # Using a lightweight, efficient model suitable for CPU
            cls._embedding_model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
        return cls._embedding_model

    @staticmethod
    def get_chroma_client(path):
        """
        Returns a persistent ChromaDB client for the given path.
        """
        return chromadb.PersistentClient(path=path)

    @staticmethod
    def get_collection(client, name):
        """
        Returns a ChromaDB collection, creating it if it doesn't exist.
        """
        return client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )
