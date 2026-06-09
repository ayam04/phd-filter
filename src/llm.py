from __future__ import annotations

import json

import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential

from .cache import cached
from .config import (
    EMBED_MODEL,
    LLM_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE,
)

_client = None
_embedder = None


def client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(base_url=OPENROUTER_BASE, api_key=OPENROUTER_API_KEY)
    return _client


def embedder():
    global _embedder
    if _embedder is None:
        from fastembed import TextEmbedding

        _embedder = TextEmbedding(model_name=EMBED_MODEL)
    return _embedder


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20))
def _complete_raw(model: str, system: str, user: str, temperature: float) -> str:
    resp = client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=8000,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or "{}"


def _coerce_dict(obj) -> dict:
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj[0]
    return {}


@cached("llm_json")
def _complete_cached(model: str, system: str, user: str, temperature: float) -> dict:
    raw = _complete_raw(model, system, user, temperature)
    try:
        return _coerce_dict(json.loads(_strip_fences(raw)))
    except json.JSONDecodeError:
        return _coerce_dict(json.loads(_strip_fences(_complete_raw(model, system, user, temperature))))


def complete_json(system: str, user: str, temperature: float = 0.0) -> dict:
    try:
        return _complete_cached(LLM_MODEL, system, user, temperature)
    except Exception:
        return {}


@cached("embed")
def _embed_cached(model: str, text: str) -> list[float]:
    vec = list(embedder().embed([text]))[0]
    return [float(x) for x in vec]


def embed(text: str) -> list[float]:
    return _embed_cached(EMBED_MODEL, text[:8000] if text else "")


def embed_many(texts: list[str]) -> list[list[float]]:
    return [embed(t) for t in texts]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = np.linalg.norm(va), np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))
