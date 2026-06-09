"""Make `import src...` work from the repo root during tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
