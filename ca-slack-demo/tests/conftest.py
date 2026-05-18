"""Pytest configuration — markers and shared fixtures."""

import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires real GCP credentials and CA agent IDs (skipped in CI without env vars)",
    )


@pytest.fixture(autouse=True)
def load_dotenv():
    """Load .env if present so integration tests work locally without manual export."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
