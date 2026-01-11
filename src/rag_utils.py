import os
# Disable tokenizer parallelism to prevent thread panics
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

from chromadb.config import Settings
import chromadb

# Try multiple embedding backends with graceful fallback
HUGGINGFACE_EMBEDDINGS_AVAILABLE = False
HuggingFaceEmbeddings = None

try:
    from langchain_huggingface import HuggingFaceEmbeddings
    HUGGINGFACE_EMBEDDINGS_AVAILABLE = True
except ImportError:
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        HUGGINGFACE_EMBEDDINGS_AVAILABLE = True
    except ImportError:
        pass

# If langchain not available, create a simple fallback using sentence_transformers
if not HUGGINGFACE_EMBEDDINGS_AVAILABLE:
    try:
        from sentence_transformers import SentenceTransformer
        
        class HuggingFaceEmbeddings:
            """Fallback embeddings using sentence_transformers directly."""
            def __init__(self, model_name="all-MiniLM-L6-v2"):
                self.model = SentenceTransformer(model_name)
            
            def embed_documents(self, texts):
                return self.model.encode(texts).tolist()
            
            def embed_query(self, text):
                return self.model.encode(text).tolist()
        
        HUGGINGFACE_EMBEDDINGS_AVAILABLE = True
    except ImportError:
        print("Warning: No embedding libraries available. Install sentence-transformers or langchain-huggingface.")

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
