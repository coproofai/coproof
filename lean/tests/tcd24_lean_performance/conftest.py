"""
Conftest for TCD-24 — Lean Worker: Performance Benchmarks & Load.

Provides a no-op `benchmark` fixture when pytest-benchmark is NOT installed,
so all benchmark tests run (calling the target function exactly once) rather
than erroring with "fixture 'benchmark' not found".

When pytest-benchmark IS installed its plugin registers the real `benchmark`
fixture, which takes precedence and provides full statistical output (min/max/
mean/stddev/OPS across multiple rounds).
"""

try:
    import pytest_benchmark  # noqa: F401 — real fixture provided by the plugin
except ImportError:
    import pytest

    class _FallbackBenchmark:
        """Minimal stand-in that calls the function once with no statistics."""

        def __call__(self, func, *args, **kwargs):
            return func(*args, **kwargs)

        def pedantic(self, func, args=(), kwargs=None, iterations=1, rounds=1, **kw):
            return func(*(args or ()), **(kwargs or {}))

    @pytest.fixture
    def benchmark():
        return _FallbackBenchmark()
