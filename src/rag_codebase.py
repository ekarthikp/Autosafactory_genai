import uuid
from src.rag_utils import RAGUtils, CODEBASE_DB_PATH
from src.knowledge import inspect_class
import autosarfactory.autosarfactory as autosarfactory

class CodebaseKnowledgeBase:
    def __init__(self):
        self.client = RAGUtils.get_chroma_client(CODEBASE_DB_PATH)
        self.collection = RAGUtils.get_collection(self.client, "codebase_knowledge")
        self.embedding_model = RAGUtils.get_embedding_model()

        # Check if we need to ingest
        if self.collection.count() == 0:
            print("Codebase Knowledge Base empty. Ingesting autosarfactory API...")
            self.ingest_codebase()
        else:
            print(f"Codebase Knowledge Base loaded. {self.collection.count()} documents indexed.")

    def ingest_codebase(self):
        """
        Iterates over autosarfactory classes, generates descriptions, and indexes them.
        """
        # Collect all class names from autosarfactory
        class_names = []
        for name in dir(autosarfactory):
            if not name.startswith('_'):
                 # We want classes that are likely AUTOSAR elements
                 # inspect_class handles validity checks
                 class_names.append(name)

        print(f"Found {len(class_names)} potential classes/objects. Processing...")

        batch_texts = []
        batch_ids = []
        batch_metadatas = []

        count = 0
        for name in class_names:
            description = inspect_class(name)
            # Skip if "not found" or trivial
            if "not found" in description or len(description) < 50:
                continue

            # We treat the entire class description as one document for now
            # because splitting it might lose context (methods need to belong to the class)

            # Additional context for embedding: split CamelCase
            # e.g. EthernetCluster -> "Ethernet Cluster"
            # This helps matching "create an ethernet cluster"

            batch_texts.append(description)
            batch_ids.append(str(uuid.uuid4()))
            batch_metadatas.append({"class_name": name, "source": "autosarfactory"})
            count += 1

            if len(batch_texts) >= 64:
                 self._add_batch(batch_ids, batch_texts, batch_metadatas)
                 batch_texts, batch_ids, batch_metadatas = [], [], []

        if batch_texts:
             self._add_batch(batch_ids, batch_texts, batch_metadatas)

        print(f"Ingestion complete. Indexed {count} classes.")

    def _add_batch(self, ids, texts, metadatas):
        embeddings = self.embedding_model.embed_documents(texts)
        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def query(self, query_text, n_results=3):
        """
        Retrieves relevant API docs for the given query.
        Implements a hybrid search (Exact Name Match + Semantic Search).
        """
        # 1. Try exact/partial name match first
        # We can't efficiently search metadata in Chroma without exact match,
        # so we'll rely on semantic search but boost it with specific queries if possible.
        # Alternatively, we can use a "where" clause if we know the class name.

        # Simple heuristic: if query looks like a CamelCase class name, try to find it specifically
        potential_class = query_text.strip()
        exact_results = {'documents': [], 'metadatas': []}

        if len(potential_class.split()) == 1 and potential_class[0].isupper():
            # Try to fetch exactly this class
            res = self.collection.get(
                where={"class_name": potential_class},
                limit=1
            )
            if res['documents']:
                exact_results['documents'].append(res['documents'][0])
                exact_results['metadatas'].append(res['metadatas'][0])

        # 2. Semantic Search
        query_embedding = self.embedding_model.embed_query(query_text)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        context = []
        seen_classes = set()

        # Add exact matches first
        if exact_results['documents']:
            for i, doc in enumerate(exact_results['documents']):
                name = exact_results['metadatas'][i].get('class_name', 'Unknown')
                if name not in seen_classes:
                    context.append(f"--- API Documentation for {name} ---\n{doc}")
                    seen_classes.add(name)

        # Add semantic matches
        if results['documents']:
            for i, doc in enumerate(results['documents'][0]):
                name = results['metadatas'][0][i].get('class_name', 'Unknown')
                if name not in seen_classes:
                    context.append(f"--- API Documentation for {name} ---\n{doc}")
                    seen_classes.add(name)

        return "\n\n".join(context)

if __name__ == "__main__":
    # Test
    kb = CodebaseKnowledgeBase()
    res = kb.query("How do I create an Ethernet Cluster?")
    print("\nSearch Result:\n", res)
