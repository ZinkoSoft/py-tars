from __future__ import annotations

"""Lightweight HyperDB for hybrid retrieval (vector + BM25 + rerank).

This module now includes automatic vector-dimension reconciliation. If the
stored vectors were created with a different embedding model (hence a
different dimensionality) than the current embedder, HyperDB will transparently
re-embed all existing documents on the next add/query to match the current
dimension. This avoids runtime errors like vstack/MatMul dimension mismatches.
"""

from dataclasses import dataclass
import logging
from typing import Any, Callable, Iterable
import gzip, pickle
import numpy as np
import bm25s
import Stemmer
from flashrank import Ranker, RerankRequest

logger = logging.getLogger("memory-worker")


def cosine_similarity(vectors: np.ndarray, q: np.ndarray) -> np.ndarray:
    v = vectors
    if v.ndim == 1:
        v = v.reshape(1, -1)
    qv = q.reshape(1, -1)
    v = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-8)
    qv = qv / (np.linalg.norm(qv, axis=1, keepdims=True) + 1e-8)
    return (v @ qv.T).ravel()


@dataclass
class HyperConfig:
    rag_strategy: str = "hybrid"  # naive | hybrid
    top_k: int = 5
    rerank_model: str | None = "ms-marco-MiniLM-L-12-v2"
    rerank_cache: str | None = "/data/flashrank_cache"


class HyperDB:
    """Hybrid doc store supporting vector and BM25 retrieval with optional rerank."""

    def __init__(self, embedding_fn: Callable[[list[str]], np.ndarray], cfg: HyperConfig | None = None):
        self.cfg = cfg or HyperConfig()
        self.embed = embedding_fn
        self.documents: list[Any] = []
        self.vectors: np.ndarray | None = None

        # BM25 components
        self.stemmer = Stemmer.Stemmer("english") if self.cfg.rag_strategy == "hybrid" else None
        self.bm25 = bm25s.BM25(method="lucene") if self.cfg.rag_strategy == "hybrid" else None
        self.corpus_texts: list[str] | None = [] if self.cfg.rag_strategy == "hybrid" else None
        self.corpus_tokens = None

        # Reranker
        self.reranker: Ranker | None = None
        if self.cfg.rerank_model:
            try:
                self.reranker = Ranker(model_name=self.cfg.rerank_model, cache_dir=self.cfg.rerank_cache)
            except Exception:
                self.reranker = None

    def _doc_to_text(self, doc: Any) -> str:
        if isinstance(doc, dict):
            # Prefer specific fields if present
            txt = ""
            if "user_input" in doc:
                txt += f"{doc['user_input']} "
            if "bot_response" in doc:
                txt += str(doc["bot_response"])  # may be non-str
            if not txt:
                txt = " ".join(str(v) for v in doc.values())
            return txt.strip()
        return str(doc)

    def _ensure_bm25(self):
        if self.cfg.rag_strategy != "hybrid":
            return
        self.corpus_texts = [self._doc_to_text(d) for d in self.documents]
        self.corpus_tokens = bm25s.tokenize(self.corpus_texts, stopwords="en", stemmer=self.stemmer)
        self.bm25.index(self.corpus_tokens)

    def add(self, docs: Iterable[Any]):
        docs = list(docs)
        if not docs:
            return
        # Generate embeddings
        texts = [self._doc_to_text(d) for d in docs]
        vecs = np.asarray(self.embed(texts), dtype=np.float32)
        if self.vectors is None:
            self.vectors = vecs
        else:
            # If dimensions differ due to an embedding model change, re-embed existing corpus
            try:
                cur_dim = int(self.vectors.shape[1]) if self.vectors.ndim == 2 else int(self.vectors.shape[-1])
                new_dim = int(vecs.shape[1]) if vecs.ndim == 2 else int(vecs.shape[-1])
            except Exception:
                cur_dim = self.vectors.shape[-1]
                new_dim = vecs.shape[-1]

            if cur_dim != new_dim:
                logger.info(f"Embedding dim changed {cur_dim} -> {new_dim}; re-embedding {len(self.documents)} existing docs")
                existing_texts = [self._doc_to_text(d) for d in self.documents]
                self.vectors = np.asarray(self.embed(existing_texts), dtype=np.float32)
            self.vectors = np.vstack([self.vectors, vecs])
        self.documents.extend(docs)
        self._ensure_bm25()

    def save(self, path: str):
        data = {"vectors": self.vectors, "documents": self.documents}
        if path.endswith(".gz"):
            with gzip.open(path, "wb") as f:
                pickle.dump(data, f)
        else:
            with open(path, "wb") as f:
                pickle.dump(data, f)

    def load(self, path: str) -> bool:
        try:
            if path.endswith(".gz"):
                with gzip.open(path, "rb") as f:
                    data = pickle.load(f)
            else:
                with open(path, "rb") as f:
                    data = pickle.load(f)
            self.vectors = data.get("vectors")
            self.documents = data.get("documents", [])
            if self.cfg.rag_strategy == "hybrid" and self.documents:
                self._ensure_bm25()
            return True
        except Exception:
            return False

    def query(self, query_text: str, top_k: int | None = None) -> list[tuple[Any, float]]:
        if not self.documents or self.vectors is None or self.vectors.size == 0:
            return []
        k = top_k or self.cfg.top_k
        # Vector search
        qv = np.asarray(self.embed([query_text])[0], dtype=np.float32)
        # Ensure dimensions are compatible; if not, re-embed entire corpus to current embedder dimension
        try:
            cur_dim = int(self.vectors.shape[1]) if self.vectors.ndim == 2 else int(self.vectors.shape[-1])
        except Exception:
            cur_dim = self.vectors.shape[-1]
        q_dim = int(qv.shape[0]) if qv.ndim == 1 else int(qv.shape[1])
        if cur_dim != q_dim:
            logger.info(f"Vector/query dim mismatch {cur_dim} vs {q_dim}; re-embedding {len(self.documents)} docs to reconcile")
            texts = [self._doc_to_text(d) for d in self.documents]
            self.vectors = np.asarray(self.embed(texts), dtype=np.float32)

        sims = cosine_similarity(self.vectors, qv)
        top_idx = np.argsort(sims)[-max(1, k * 2):][::-1]

        candidates = [(self.documents[i], float(sims[i])) for i in top_idx]

        if self.cfg.rag_strategy == "hybrid" and self.bm25 is not None:
            # BM25 retrieve
            qtok = bm25s.tokenize([query_text], stopwords="en", stemmer=self.stemmer)
            bm_idx, bm_scores = self.bm25.retrieve(qtok, k=min(len(self.documents), max(1, k * 2)))
            try:
                bm_idx = bm_idx[0]; bm_scores = bm_scores[0]
            except Exception:
                bm_idx, bm_scores = [], []

            # Reciprocal rank fusion
            v_ranks = {i: r + 1 for r, i in enumerate([i for i in top_idx])}
            b_ranks = {int(i): r + 1 for r, i in enumerate(list(bm_idx))}
            all_ids = set(v_ranks) | set(b_ranks)
            rrf = {i: (1 / (60 + v_ranks.get(i, len(self.documents) + 1))) + (1 / (60 + b_ranks.get(i, len(self.documents) + 1))) for i in all_ids}
            fused = sorted(rrf.items(), key=lambda x: x[1], reverse=True)[: max(k * 2, k)]
            candidates = [(self.documents[i], rrf[i]) for i, _ in fused]

        # Optional rerank
        if self.reranker and candidates:
            passages = [{"id": idx, "text": self._doc_to_text(doc), "meta": {}} for idx, (doc, _) in enumerate(candidates)]
            try:
                results = self.reranker.rerank(RerankRequest(query=query_text, passages=passages))
                order = sorted(((r["id"], r.get("score", 0.0)) for r in results), key=lambda x: x[1], reverse=True)
                reranked = [candidates[i] for i, _ in order[:k]]
                return reranked
            except Exception:
                pass

        return candidates[:k]
