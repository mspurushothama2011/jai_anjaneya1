import sys
import os

# Ensure the project root directory is in the Python module search path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))  # ✅ Add main project directory to sys.path

from app import app  # ✅ Ensure Flask finds app.py

if __name__ == "__main__":
    app.run(debug=True, port=5000)
