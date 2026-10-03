"""
Local 384-dimensional vector embedder.

Uses ONNX Runtime + Hugging Face Tokenizers for real sentence-transformers/all-MiniLM-L6-v2
embeddings without PyTorch overhead.
Embeddings are normalized float32 bytes for SQLite BLOB storage.
Cosine similarity is computed in-process using numpy.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

_session: Any = None
_tokenizer: Any = None
_load_failed: bool = False


def _load_onnx_model():
    global _session, _tokenizer, _load_failed
    if _load_failed:
        return None, None
    if _session is not None and _tokenizer is not None:
        return _session, _tokenizer

    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer
        from huggingface_hub import hf_hub_download

        logger.info("loading_onnx_embedding_model name=%s", settings.embedding_model)
        tokenizer = AutoTokenizer.from_pretrained(f"sentence-transformers/{settings.embedding_model}")
        model_path = hf_hub_download(f"sentence-transformers/{settings.embedding_model}", "onnx/model.onnx")
        session = ort.InferenceSession(model_path)

        _session = session
        _tokenizer = tokenizer
        logger.info("onnx_embedding_model_loaded dims=%d", settings.embedding_dims)
        return _session, _tokenizer

    except Exception as exc:
        logger.warning(
            "onnx_embedder_load_failed err=%s — using deterministic fallback embedder",
            exc
        )
        _load_failed = True
        return None, None


def _mean_pooling(model_output: Any, attention_mask: np.ndarray) -> np.ndarray:
    """Mean Pooling — take attention mask into account for correct averaging."""
    token_embeddings = model_output[0]  # First element contains all token embeddings
    input_mask_expanded = np.expand_dims(attention_mask, -1).astype(token_embeddings.dtype)
    sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
    sum_mask = np.clip(input_mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
    return sum_embeddings / sum_mask


def _fallback_embed(text: str, dims: int = 384) -> np.ndarray:
    """Deterministic 384-dim fallback vector for testing environments."""
    import hashlib
    text_clean = text.strip().lower()
    vec = np.zeros(dims, dtype=np.float32)
    words = text_clean.split() or ["empty"]

    for word in words:
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        idx = h % dims
        val = ((h >> 8) % 1000) / 500.0 - 1.0
        vec[idx] += val

    norm = np.linalg.norm(vec)
    return (vec / norm) if norm > 0 else vec


async def embed_text(text: str) -> bytes:
    """
    Embed text using real ONNX MiniLM model and return float32 bytes.
    Runs in a thread executor to avoid blocking the event loop.
    """
    session, tokenizer = await asyncio.to_thread(_load_onnx_model)
    if session is not None and tokenizer is not None:
        def _run_onnx():
            inputs = tokenizer(
                text,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="np"
            )
            ort_inputs = {k: v.astype(np.int64) for k, v in inputs.items()}
            if "token_type_ids" not in ort_inputs:
                ort_inputs["token_type_ids"] = np.zeros_like(ort_inputs["input_ids"])
            outputs = session.run(None, ort_inputs)
            pooled = _mean_pooling(outputs, ort_inputs["attention_mask"])
            norm = np.linalg.norm(pooled[0])
            normalized = pooled[0] / max(norm, 1e-9)
            return normalized.astype(np.float32).tobytes()

        return await asyncio.to_thread(_run_onnx)

    # Fallback if model load fails
    vec = _fallback_embed(text, dims=settings.embedding_dims)
    return vec.astype(np.float32).tobytes()


def cosine_similarity(a: bytes, b: bytes) -> float:
    """Cosine similarity between two float32 BLOB embeddings."""
    va = np.frombuffer(a, dtype=np.float32)
    vb = np.frombuffer(b, dtype=np.float32)
    return float(np.dot(va, vb))


def rank_by_similarity(
    query_embedding: bytes,
    candidates: list[tuple[int, bytes]],
    top_k: int = 10,
) -> list[tuple[int, float]]:
    """Return [(item_id, score)] sorted by cosine similarity descending."""
    if not candidates:
        return []
    q = np.frombuffer(query_embedding, dtype=np.float32)
    ids, vecs = zip(*candidates)
    matrix = np.vstack([np.frombuffer(v, dtype=np.float32) for v in vecs])
    scores = matrix @ q
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [(ids[i], float(scores[i])) for i in top_indices]
