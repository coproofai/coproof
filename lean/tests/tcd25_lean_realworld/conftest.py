"""
Conftest for TCD-25 — Lean Worker: Real-World Mathlib Scenario Tests.

Provides a no-op `benchmark` fixture when pytest-benchmark is NOT installed,
so TC-25-01 runs (calling the function once) rather than failing with
"fixture 'benchmark' not found".

When pytest-benchmark IS installed its plugin registers the real `benchmark`
fixture, which takes precedence and provides full statistical output.
"""

try:
    import pytest_benchmark  # noqa: F401 — real fixture provided by the plugin
except ImportError:
    import pytest

    class _FallbackBenchmark:
        """Minimal stand-in that calls the function once with no statistics."""

        extra_info: dict = {}

        def __call__(self, func, *args, **kwargs):
            return func(*args, **kwargs)

        def pedantic(self, func, args=(), kwargs=None, iterations=1, rounds=1, **kw):
            return func(*(args or ()), **(kwargs or {}))

    @pytest.fixture
    def benchmark():
        fb = _FallbackBenchmark()
        fb.extra_info = {}
        return fb
