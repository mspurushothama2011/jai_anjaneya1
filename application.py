import sys
import os
from dotenv import load_dotenv

# Load environment variables (mostly for local, EB handles its own env vars)
load_dotenv()

# Add the main project directory to sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# AWS Elastic Beanstalk expects an object named "application" inside a file named "application.py"
from app import app as application

if __name__ == "__main__":
    application.run()
