import chromadb
from typing import List, Dict


class MediChainRAG:
    """
    MediChain RAG Engine
    Handles semantic search across local medical knowledge base with citation tracking.
    """
    def __init__(self, db_path: str = "./chroma_data", collection_name: str = "medical_kb"):
        # Connect to the persistent database
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_collection(name=collection_name)
        print(f"MediChain RAG initialized. Current vector count: {self.collection.count()}")

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        Execute semantic search and return structured results.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )

        formatted_results = []
        for i in range(len(results['documents'][0])):
            formatted_results.append({
                "content": results['documents'][0][i],
                "source": results['metadatas'][0][i].get('title', 'Unknown Source'),
                "id": results['ids'][0][i]
            })
        return formatted_results

    def get_context_for_llm(self, query: str, top_k: int = 3) -> str:
        """
        Convert search results into a prompt-ready string for LLM (with citations).
        """
        evidences = self.search(query, top_k)
        context = "Here is the medical evidence retrieved from authoritative sources:\n\n"

        for i, ev in enumerate(evidences):
            context += f"--- Evidence [{i+1}] ---\n"
            context += f"Source: {ev['source']}\n"
            context += f"Content: {ev['content']}\n\n"

        context += "Please use the evidence above to answer the user's question. If the evidence is insufficient, please state so."
        return context


# Quick Test Script
if __name__ == "__main__":
    rag = MediChainRAG()
    # Use the encapsulated search method which returns a clean List of Dicts
    formatted_results = rag.search("pediatric pneumonia")

    if formatted_results:
        print(f"Top result source: {formatted_results[0]['source']}")
