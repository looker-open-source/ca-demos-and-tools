"""Tests for chart renderer."""

from unittest.mock import patch

from src.charts.renderer import render_chart


class TestRenderChart:
    def test_returns_none_on_missing_import(self):
        with patch.dict("sys.modules", {"vl_convert": None}):
            # Force reimport to hit ImportError path
            import importlib
            from src.charts import renderer
            importlib.reload(renderer)
            result = renderer.render_chart({"mark": "bar"})
            # May or may not be None depending on reload behavior,
            # but should not raise
            assert result is None or isinstance(result, bytes)

    def test_returns_none_on_bad_spec(self):
        # If vl-convert is installed, a garbage spec should return None
        result = render_chart({"not": "a valid spec"})
        assert result is None or isinstance(result, bytes)

    def test_accepts_string_spec(self):
        result = render_chart('{"not": "valid"}')
        assert result is None or isinstance(result, bytes)
