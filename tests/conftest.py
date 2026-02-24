"""
Shared pytest fixtures and configuration.

conftest.py is auto-loaded by pytest — fixtures defined here are available
to all test files without explicit imports.
"""

import os
import sys

# Add the service directory to the path so tests can import service modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "service"))
