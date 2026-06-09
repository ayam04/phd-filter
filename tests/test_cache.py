from src import cache


def test_cache_hits_function_once(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    calls = {"n": 0}

    @cache.cached("unit")
    def expensive(x):
        calls["n"] += 1
        return {"v": x * 2}

    assert expensive(3) == {"v": 6}
    assert expensive(3) == {"v": 6}   # served from cache
    assert calls["n"] == 1            # underlying fn ran only once


def test_cache_key_varies_with_args(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    calls = {"n": 0}

    @cache.cached("unit2")
    def f(x):
        calls["n"] += 1
        return x

    f(1)
    f(2)
    assert calls["n"] == 2            # different args -> different keys


def test_cache_stores_none(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_DIR", tmp_path)
    calls = {"n": 0}

    @cache.cached("unit3")
    def maybe():
        calls["n"] += 1
        return None

    assert maybe() is None
    assert maybe() is None
    assert calls["n"] == 1            # None is cached via file existence
