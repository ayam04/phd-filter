import pytest

from src import llm
from src.config import OPENROUTER_API_KEY


@pytest.mark.live
@pytest.mark.skipif(not OPENROUTER_API_KEY, reason="no OPENROUTER_API_KEY")
def test_complete_json_live():
    out = llm.complete_json(
        system="You output strict JSON.",
        user='Return JSON {"discipline": "...", "is_stem": true/false} for the field: clinical psychology.',
    )
    assert isinstance(out, dict)
    assert "discipline" in out


@pytest.mark.live
def test_embed_and_cosine_live():
    a = llm.embed("post-traumatic stress disorder treatment in veterans")
    b = llm.embed("PTSD therapy and trauma recovery for military personnel")
    c = llm.embed("single-cell RNA sequencing of plant root tissue")
    assert len(a) > 100
    assert llm.cosine(a, b) > llm.cosine(a, c)
