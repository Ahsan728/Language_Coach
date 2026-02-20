# wsgi.py — used by PythonAnywhere
# In PythonAnywhere's WSGI config file, point to this file
# and set: application = app
import sys
import os

# Add project root to Python path (PythonAnywhere needs this)
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from app import app as application  # noqa: F401
