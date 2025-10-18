"""
Shared fixtures for config-manager tests.
"""

import pytest
import tempfile
import os
from pathlib import Path

from config_manager.auth import initialize_token_store, Role
from tars.config.database import ConfigDatabase
from fastapi.testclient import TestClient


@pytest.fixture
async def db():
    """Create a temporary database for testing."""
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_config.db"
        database = ConfigDatabase(str(db_path))
        await database.connect()
        await database.initialize_schema()
        yield database
        await database.close()
        # Cleanup happens automatically when context manager exits


@pytest.fixture
def test_tokens():
    """Initialize test tokens."""
    token_store = initialize_token_store()
    
    # Create test tokens
    admin_token = token_store.create_token("test-admin-token", "admin", Role.ADMIN)
    write_token = token_store.create_token("test-write-token", "writer", Role.WRITE)
    readonly_token = token_store.create_token("test-readonly-token", "reader", Role.READ)
    
    return {
        "admin": "test-admin-token",
        "write": "test-write-token",
        "readonly": "test-readonly-token",
    }


@pytest.fixture
def admin_token(test_tokens):
    """Get admin token."""
    return test_tokens["admin"]


@pytest.fixture
def write_token(test_tokens):
    """Get write token."""
    return test_tokens["write"]


@pytest.fixture
def readonly_token(test_tokens):
    """Get readonly token."""
    return test_tokens["readonly"]


@pytest.fixture
def admin_csrf_token():
    """Get CSRF token for admin (using token name as CSRF for testing)."""
    return "test-admin-token"


@pytest.fixture
def write_csrf_token():
    """Get CSRF token for write user."""
    return "test-write-token"


@pytest.fixture
def readonly_csrf_token():
    """Get CSRF token for readonly user."""
    return "test-readonly-token"


@pytest.fixture
def client(db, test_tokens):
    """Create a test client with initialized database and tokens."""
    from config_manager.__main__ import create_app
    
    app = create_app()
    
    # Inject database into app state
    app.state.database = db
    
    return TestClient(app)
