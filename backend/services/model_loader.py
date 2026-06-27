import json
import logging
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.core.config import (
    ALLOW_MODEL_DOWNLOADS,
    FINE_TUNE_METADATA_PATH,
    FINE_TUNED_MODEL_FALLBACK_PATH,
    FINE_TUNED_MODEL_PATH,
    SENTENCE_TRANSFORMER_MODEL,
)

logger = logging.getLogger("ats_resume_scorer")


class LocalHashingEmbedder:
    """Small offline fallback with the same encode() shape used by the app."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def _encode_one(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        tokens = re.findall(r"[a-zA-Z0-9+#.]+", str(text).lower())

        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def encode(
        self,
        sentences: str | Iterable[str],
        *_args,
        convert_to_tensor: bool = False,
        normalize_embeddings: bool = False,
        **_kwargs,
    ):
        if isinstance(sentences, str):
            return self._encode_one(sentences)

        vectors = np.vstack([self._encode_one(sentence) for sentence in sentences])
        if normalize_embeddings:
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            vectors = np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms != 0)
        return vectors


def _looks_like_sentence_transformer(path: Path) -> bool:
    """Return True when a folder has the files SentenceTransformer expects."""
    if not path.is_dir():
        return False

    required_markers = ("modules.json", "config_sentence_transformers.json")
    if any((path / marker).is_file() for marker in required_markers):
        return True

    transformer_dir = path / "0_Transformer"
    return transformer_dir.is_dir() and (
        (transformer_dir / "config.json").is_file()
        or (transformer_dir / "tokenizer_config.json").is_file()
    )


def _load_metadata() -> Dict[str, Any]:
    metadata_path = Path(FINE_TUNE_METADATA_PATH)
    if not metadata_path.is_file():
        return {}

    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Could not read fine-tune metadata from %s: %s", metadata_path, exc)
        return {}


def load_sentence_embedder() -> Tuple[Any, Dict[str, Any]]:
    """Load the fine-tuned resume/JD model when available, otherwise the base model."""
    metadata = _load_metadata()

    candidate_paths = [
        Path(FINE_TUNED_MODEL_PATH),
        Path(FINE_TUNED_MODEL_FALLBACK_PATH),
    ]

    for model_path in candidate_paths:
        if _looks_like_sentence_transformer(model_path):
            logger.info("Loading fine-tuned SentenceTransformer from %s", model_path)
            try:
                return SentenceTransformer(
                    str(model_path),
                    local_files_only=not ALLOW_MODEL_DOWNLOADS,
                ), {
                    "source": "fine_tuned",
                    "model_path": str(model_path),
                    "metadata": metadata,
                }
            except Exception as exc:
                logger.warning("Could not load fine-tuned model from %s: %s", model_path, exc)

    logger.warning(
        "Fine-tuned model folder not found. Falling back to SentenceTransformer '%s'.",
        SENTENCE_TRANSFORMER_MODEL,
    )
    try:
        return SentenceTransformer(
            SENTENCE_TRANSFORMER_MODEL,
            local_files_only=not ALLOW_MODEL_DOWNLOADS,
        ), {
            "source": "base_model",
            "model_name": SENTENCE_TRANSFORMER_MODEL,
            "expected_fine_tuned_paths": [str(path) for path in candidate_paths],
            "metadata": metadata,
        }
    except Exception as exc:
        logger.warning("Could not load base SentenceTransformer: %s", exc)
        return LocalHashingEmbedder(), {
            "source": "offline_hashing_fallback",
            "reason": str(exc),
            "expected_fine_tuned_paths": [str(path) for path in candidate_paths],
            "metadata": metadata,
        }
