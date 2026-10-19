# MediChain Knowledge Base

## Quick Start

Two medical corpora ready for RAG pipeline integration with ChromaDB.

### 1. StatPearls (Primary - Use This)
- **File:** `statpearls_hanyang/statpearls_all.jsonl`
- **Size:** 262,407 chunks, ~464MB
- **Source:** StatPearls via NCBI Bookshelf (CC BY-NC-ND 4.0)
- **Coverage:** 10,676 clinical articles, all major specialties
- **Avg tokens/chunk:** ~234
- **Best for:** Clinical diagnostic reasoning, evidence-based citations

### 2. Medical Textbooks (Supplementary)
- **File:** `textbooks_chunks/textbooks_all.jsonl`
- **Size:** 125,847 chunks, ~210MB
- **Source:** MedRAG project (18 USMLE textbooks)
- **Avg tokens/chunk:** ~182
- **Best for:** General medical knowledge, MMLU benchmarking

## Data Format

Each line is a JSON object:
```json
{
  "id": "49438",
  "title": "community-acquired-pneumonia-in-children-clinical-features-and-diagnosis - CLINICAL PRESENTATION",
  "contents": "The clinical presentation of childhood pneumonia varies depending upon..."
}
```

- `id` -- unique chunk identifier
- `title` -- article name + section hierarchy (use as citation source)
- `contents` -- the actual text content to embed and retrieve

## Specialty Coverage (StatPearls)

| Specialty | Articles |
|-----------|----------|
| Internal Medicine | 450+ |
| Cardiology | 512+ |
| Respiratory | 484+ |
| Emergency Medicine | 340+ |
| Neurology | 157+ |

## How to Load into ChromaDB

```python
import json
import chromadb

client = chromadb.PersistentClient(path="./chroma_data")
collection = client.get_or_create_collection(
    name="medical_kb",
    metadata={"hnsw:space": "cosine"}
)

# Load StatPearls
batch_size = 500
docs, ids, metadatas = [], [], []

with open("statpearls_hanyang/statpearls_all.jsonl") as f:
    for line in f:
        item = json.loads(line)
        docs.append(item["contents"])
        ids.append(f"sp_{item['id']}")
        metadatas.append({"source": "StatPearls", "title": item["title"]})

        if len(docs) >= batch_size:
            collection.add(documents=docs, ids=ids, metadatas=metadatas)
            docs, ids, metadatas = [], [], []

    if docs:
        collection.add(documents=docs, ids=ids, metadatas=metadatas)
```

Note: ChromaDB uses `all-MiniLM-L6-v2` by default for embedding.
For better medical domain performance, consider using `PubMedBert` or `MedCPT` embeddings.

## References

- MedRAG: https://github.com/Teddy-XiongGZ/MedRAG
- Paper: "Benchmarking Retrieval-Augmented Generation for Medicine" (ACL 2024)
- StatPearls: https://www.ncbi.nlm.nih.gov/books/NBK430685/
- HanyangMed dataset: https://huggingface.co/datasets/HanyangMed/statpearls
