import json
import logging
from pathlib import Path

import chromadb

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHROMA_DIR = Path(__file__).resolve().parent.parent / "chroma_data"

# Max chunks to load (full dataset is 388k — too slow for dev startup)
MAX_CHUNKS = 10000


class KnowledgeBase:
    def __init__(self, persist_dir: str | None = None):
        if persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            chroma_dir = str(CHROMA_DIR)
            try:
                self._client = chromadb.PersistentClient(path=chroma_dir)
            except Exception:
                logger.warning("PersistentClient failed, using EphemeralClient")
                self._client = chromadb.EphemeralClient()
        self._collection = self._client.get_or_create_collection(
            name="medical_kb",
            metadata={"hnsw:space": "cosine"},
        )

    def load(self, json_path: str | None = None) -> int:
        """Load medical knowledge base from JSONL files into ChromaDB.

        Supports both JSON (list) and JSONL (one object per line) formats.
        Fields: id, title, contents (or content or text_for_embedding).
        """
        # Check if already loaded
        existing_count = self._collection.count()
        if existing_count > 0:
            logger.info("Collection already has %d entries, skipping load.", existing_count)
            return existing_count

        # Find data files
        if json_path:
            files = [Path(json_path)]
        else:
            files = []
            # Prefer JSONL files in data/ directory
            for name in ["statpearls_all.jsonl", "textbooks_all.jsonl", "medical_kb.json"]:
                p = DATA_DIR / name
                if p.exists():
                    files.append(p)
            if not files:
                logger.warning("No knowledge base files found in %s", DATA_DIR)
                return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []
        total_loaded = 0

        for filepath in files:
            logger.info("Loading knowledge base from %s ...", filepath.name)
            try:
                if filepath.suffix == ".jsonl":
                    entries = self._read_jsonl(filepath)
                else:
                    with open(filepath, encoding="utf-8") as f:
                        entries = json.load(f)
            except Exception as e:
                logger.error("Failed to read %s: %s", filepath, e)
                continue

            for entry in entries:
                if total_loaded >= MAX_CHUNKS:
                    break

                doc_id = str(entry.get("id", f"doc_{total_loaded}"))
                # Support multiple field names
                text = entry.get("contents") or entry.get("content") or entry.get("text_for_embedding") or ""
                # Guard against explicit "title": null in the JSON —
                # .get("title", "") returns None in that case, and Chroma metadata rejects None.
                title = entry.get("title") or ""

                if not text or len(text.strip()) < 20:
                    continue

                ids.append(f"kb_{doc_id}")
                documents.append(text[:2000])  # Truncate very long chunks
                metadatas.append({
                    "title": title,
                    "source": "StatPearls" if "statpearls" in filepath.name else "MedRAG",
                })
                total_loaded += 1

            if total_loaded >= MAX_CHUNKS:
                logger.info("Reached max chunks (%d), stopping.", MAX_CHUNKS)
                break

        if not ids:
            logger.warning("No valid entries found in knowledge base files")
            return 0

        # Load into ChromaDB in batches
        batch_size = 500
        for start in range(0, len(ids), batch_size):
            end = min(start + batch_size, len(ids))
            self._collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
            if (start // batch_size) % 10 == 0:
                logger.info("  Loaded %d / %d chunks...", end, len(ids))

        logger.info("Knowledge base loaded: %d chunks from %d files.", len(ids), len(files))
        return len(ids)

    def _read_jsonl(self, path: Path) -> list[dict]:
        """Read a JSONL file (one JSON object per line)."""
        entries = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(entries) >= MAX_CHUNKS:
                    break
        return entries

    def query(self, query_text: str, n_results: int = 5) -> list[dict]:
        """Query the knowledge base and return relevant entries."""
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query_text],
            n_results=min(n_results, self._collection.count()),
        )

        entries = []
        if results and results["metadatas"]:
            for i, meta in enumerate(results["metadatas"][0]):
                entry = dict(meta)
                if results["documents"]:
                    entry["text"] = results["documents"][0][i]
                if results["distances"]:
                    entry["distance"] = results["distances"][0][i]
                entries.append(entry)

        return entries
