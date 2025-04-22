import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Ensure the project root directory is in the Python module search path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))  # ✅ Add main project directory to sys.path

from app import app  # ✅ Ensure Flask finds app.py

# For Render deployment and local development
if __name__ == "__main__":
    # Set debug mode only in development, not in production
    debug_mode = os.environ.get('FLASK_ENV', 'development') != 'production'
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)
