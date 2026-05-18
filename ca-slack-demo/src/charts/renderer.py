"""Render Vega-Lite chart specs to PNG images."""

from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


def render_chart(spec: dict | str, scale: float = 2.0) -> bytes | None:
    """Render a Vega-Lite spec to PNG bytes.

    Returns None if rendering fails (malformed spec, missing vl-convert, etc.)
    """
    try:
        import vl_convert as vlc
    except ImportError:
        log.warning("vl-convert-python not installed — chart rendering disabled")
        return None

    try:
        if isinstance(spec, str):
            spec = json.loads(spec)
        return vlc.vegalite_to_png(vl_spec=spec, scale=scale)
    except Exception:
        log.exception("Failed to render Vega-Lite chart")
        return None
