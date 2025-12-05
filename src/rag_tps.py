import os
import uuid
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.rag_utils import RAGUtils, TPS_DB_PATH

class TPSKnowledgeBase:
    def __init__(self, pdf_path="tmp/file_attachments/AUTOSAR_CP_TPS_SystemTemplate.pdf"):
        self.pdf_path = pdf_path
        self.client = RAGUtils.get_chroma_client(TPS_DB_PATH)
        self.collection = RAGUtils.get_collection(self.client, "tps_knowledge")
        self.embedding_model = RAGUtils.get_embedding_model()

        # Check if we need to ingest
        if self.collection.count() == 0:
            print(f"TPS Knowledge Base empty. Ingesting {self.pdf_path}...")
            self.ingest_pdf()
        else:
            print(f"TPS Knowledge Base loaded. {self.collection.count()} documents indexed.")

    def ingest_pdf(self):
        """
        Loads the PDF, chunks it, and indexes it into ChromaDB.
        """
        if not os.path.exists(self.pdf_path):
             # Try alternate path if default fails
             alt_paths = [
                 "AUTOSAR_CP_TPS_SystemTemplate.pdf",
                 "/tmp/file_attachments/kk/AUTOSAR_CP_TPS_SystemTemplate.pdf",
                 "tmp/file_attachments/kk/AUTOSAR_CP_TPS_SystemTemplate.pdf"
             ]
             found = False
             for alt in alt_paths:
                 if os.path.exists(alt):
                     self.pdf_path = alt
                     found = True
                     break

             if not found:
                 print(f"Warning: TPS PDF not found. Tried {self.pdf_path} and alternates. Skipping ingestion.")
                 return

        loader = PyPDFLoader(self.pdf_path)
        documents = loader.load()

        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
        chunks = text_splitter.split_documents(documents)

        print(f"Split PDF into {len(chunks)} chunks. Embedding...")

        # Prepare for Chroma
        ids = [str(uuid.uuid4()) for _ in chunks]
        texts = [chunk.page_content for chunk in chunks]
        metadatas = [{"source": self.pdf_path, "page": chunk.metadata.get("page", 0)} for chunk in chunks]

        # Generate embeddings in batches to avoid memory issues
        batch_size = 32
        for i in range(0, len(chunks), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            batch_metadatas = metadatas[i:i+batch_size]

            embeddings = self.embedding_model.embed_documents(batch_texts)
            self.collection.add(
                ids=batch_ids,
                documents=batch_texts,
                embeddings=embeddings,
                metadatas=batch_metadatas
            )

        print("Ingestion complete.")

    def query(self, query_text, n_results=3):
        """
        Retrieves relevant context for the given query.
        """
        query_embedding = self.embedding_model.embed_query(query_text)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        # Format results
        context = []
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                context.append(f"--- Context {i+1} ---\n{doc}")

        return "\n\n".join(context)

if __name__ == "__main__":
    # Test
    kb = TPSKnowledgeBase()
    res = kb.query("What is an Ethernet Cluster?")
    print("\nSearch Result:\n", res)
