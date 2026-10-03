"""Tests for vector embedder module."""
import pytest
import numpy as np
from app.ai.embedder import embed_text, cosine_similarity, _mean_pooling


@pytest.mark.asyncio
async def test_embedder_similarity_thresholds():
    # Sentences from requirement specification
    s1 = "A man is eating food."
    s2 = "A man is eating a piece of bread."
    s3 = "The girl is carrying a baby."

    emb1 = await embed_text(s1)
    emb2 = await embed_text(s2)
    emb3 = await embed_text(s3)

    assert len(emb1) == 384 * 4  # 384 float32 bytes
    assert len(emb2) == 384 * 4
    assert len(emb3) == 384 * 4

    # Verify L2 normalization
    v1 = np.frombuffer(emb1, dtype=np.float32)
    norm1 = np.linalg.norm(v1)
    assert pytest.approx(norm1, abs=1e-5) == 1.0

    score_similar = cosine_similarity(emb1, emb2)
    score_dissimilar = cosine_similarity(emb1, emb3)

    assert score_similar > 0.6, f"Expected > 0.6, got {score_similar}"
    assert score_dissimilar < 0.25, f"Expected < 0.25, got {score_dissimilar}"


def test_mean_pooling_uses_attention_mask():
    # Mock model outputs (1 batch, 3 tokens, 4 features)
    token_embeddings = np.array([
        [[1.0, 2.0, 3.0, 4.0],
         [5.0, 6.0, 7.0, 8.0],
         [100.0, 100.0, 100.0, 100.0]]  # Padded token
    ], dtype=np.float32)

    # Attention mask: mask out third token (0)
    attention_mask = np.array([[1, 1, 0]], dtype=np.int64)

    pooled = _mean_pooling([token_embeddings], attention_mask)
    expected = np.array([[3.0, 4.0, 5.0, 6.0]], dtype=np.float32)

    np.testing.assert_allclose(pooled, expected, rtol=1e-5)
