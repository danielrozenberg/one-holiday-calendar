from one_holiday_calendar import cache


def _builder(value: bytes):
    calls = []

    def build() -> bytes:
        calls.append(value)
        return value

    return build, calls


def test_hit_does_not_rebuild():
    responses = cache.ByteCache(100)
    build, calls = _builder(b"x" * 10)

    assert responses.get("a", build) == b"x" * 10
    assert responses.get("a", build) == b"x" * 10
    assert len(calls) == 1


def test_evicts_least_recently_used_to_fit_budget():
    responses = cache.ByteCache(25)
    responses.get("a", lambda: b"a" * 10)
    responses.get("b", lambda: b"b" * 10)
    responses.get("a", lambda: b"unused")
    responses.get("c", lambda: b"c" * 10)

    rebuilt_b, calls_b = _builder(b"b" * 10)
    rebuilt_a, calls_a = _builder(b"a" * 10)
    responses.get("a", rebuilt_a)
    responses.get("b", rebuilt_b)

    assert calls_a == []
    assert calls_b == [b"b" * 10]
    assert responses.size <= 25


def test_value_larger_than_budget_is_not_kept():
    responses = cache.ByteCache(5)
    responses.get("small", lambda: b"123")
    build, calls = _builder(b"x" * 10)

    assert responses.get("big", build) == b"x" * 10
    responses.get("big", build)
    assert len(calls) == 2
    assert responses.size == 3


def test_clear():
    responses = cache.ByteCache(100)
    build, calls = _builder(b"x")
    responses.get("a", build)

    responses.clear()
    responses.get("a", build)

    assert len(calls) == 2
