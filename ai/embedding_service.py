"""Local sentence embeddings (all-MiniLM-L6-v2 via fastembed/ONNX, no PyTorch)."""

import asyncio
import math
import threading
from typing import List, Optional

from ai.interfaces import BaseEmbeddingService

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class MiniLMEmbedder(BaseEmbeddingService):
    """Returns 384 normalised floats. The model loads once per process, on first use."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding  # imported late so importing ai stays cheap

                self._model = TextEmbedding(model_name=self.model_name)
            return self._model

    def _embed_sync(self, texts: List[str]) -> List[List[float]]:
        vectors = []
        for raw in self._load().embed(texts):
            vector = [float(x) for x in raw]
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            vectors.append([x / norm for x in vector])
        return vectors

    async def embed(self, text: str) -> List[float]:
        return (await asyncio.to_thread(self._embed_sync, [text]))[0]

    async def embed_many(self, texts: List[str]) -> List[List[float]]:
        return await asyncio.to_thread(self._embed_sync, texts) if texts else []
