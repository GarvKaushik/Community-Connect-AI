from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np

PROGRAMS_PATH = Path(__file__).with_name("knowledge_base") / "programs.json"
MODEL_DIR = Path(__file__).with_name("models") / "embeddings"
EMBEDDING_REPO = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.28"))
TOP_K = 3

CATEGORIES = (
    "education",
    "healthcare",
    "financial_assistance",
    "employment",
    "disability",
    "women_child_welfare",
    "food",
)
NATIONWIDE = "all india"


class Embedder:
    """Multilingual sentence embeddings via onnxruntime. Hindi and English text share one
    vector space, so a Hindi question can match an English program description."""

    def __init__(self) -> None:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        model_path = hf_hub_download(EMBEDDING_REPO, "onnx/model.onnx", cache_dir=MODEL_DIR)
        tokenizer_path = hf_hub_download(EMBEDDING_REPO, "tokenizer.json", cache_dir=MODEL_DIR)
        self._tokenizer = Tokenizer.from_file(tokenizer_path)
        self._tokenizer.enable_truncation(max_length=256)
        self._tokenizer.enable_padding(pad_id=self._tokenizer.token_to_id("<pad>"), pad_token="<pad>")
        self._session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self._inputs = {item.name for item in self._session.get_inputs()}

    def embed(self, texts: list[str]) -> np.ndarray:
        encodings = self._tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in encodings], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._inputs:
            feeds["token_type_ids"] = np.zeros_like(ids)
        tokens = self._session.run(None, feeds)[0]
        weights = mask[..., None].astype(np.float32)
        pooled = (tokens * weights).sum(axis=1) / np.maximum(weights.sum(axis=1), 1e-9)
        return pooled / np.linalg.norm(pooled, axis=1, keepdims=True)


def program_passages(program: dict) -> list[str]:
    """Short passages, one per field. Embedding fields separately scores much better than
    one long passage, where the details dilute each other."""
    category = program["category"].replace("_", " ")
    passages = [f"{program['name']}. {category}. {program['description']}"]
    passages += [f"{category}: {program[field]}" for field in ("eligibility", "benefits") if program[field]]
    return passages


def _words(text: str) -> str:
    return " " + " ".join(re.findall(r"\w+", text.lower())) + " "


def location_matches(program: dict, location: str | None) -> bool:
    if not location:
        return True
    wanted = _words(location)
    return any(
        place.lower() == NATIONWIDE or _words(place) in wanted for place in program["locations"]
    )


def age_matches(program: dict, age: int | None) -> bool:
    if age is None:
        return True
    if program["min_age"] is not None and age < program["min_age"]:
        return False
    if program["max_age"] is not None and age > program["max_age"]:
        return False
    return True


class ProgramIndex:
    """The knowledge base held in memory: a few embedded passages per program, searched with
    cosine similarity after metadata filters. Fine for hundreds of programs; swap in a vector
    database such as Qdrant if the knowledge base grows to many thousands of documents."""

    def __init__(self, embedder: Embedder, programs_path: Path = PROGRAMS_PATH) -> None:
        self._embedder = embedder
        self.programs: list[dict] = json.loads(programs_path.read_text(encoding="utf-8"))
        owners, texts = [], []
        for index, program in enumerate(self.programs):
            for passage in program_passages(program):
                owners.append(index)
                texts.append(passage)
        self._owners = np.array(owners)
        self._vectors = embedder.embed(texts)

    def search(
        self,
        query: str,
        category: str | None = None,
        location: str | None = None,
        age: int | None = None,
        level: str | None = None,
    ) -> list[dict]:
        """Return up to TOP_K programs, best first, each with a `score`. Returns an empty
        list when nothing is similar enough, so the agent never gets a weak match.

        `level` ("school" or "college") only excludes education programs tagged with a
        different level; programs without a level are always kept."""
        candidates = {
            index
            for index, program in enumerate(self.programs)
            if (not category or program["category"] == category)
            and (not level or program.get("level") in (None, level))
            and location_matches(program, location)
            and age_matches(program, age)
        }
        if not candidates:
            return []

        scores = self._vectors @ self._embedder.embed([query])[0]
        best: dict[int, float] = {}
        for owner, score in zip(self._owners.tolist(), scores.tolist()):
            if owner in candidates and score > best.get(owner, -1.0):
                best[owner] = score
        ranked = sorted(best.items(), key=lambda item: item[1], reverse=True)
        return [
            {**self.programs[index], "score": round(score, 3)}
            for index, score in ranked[:TOP_K]
            if score >= MIN_SCORE
        ]
