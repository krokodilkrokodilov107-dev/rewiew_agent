import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MIN_REVIEWS = 10
MAX_REVIEWS = 1000
MIN_REVIEW_LENGTH = 15
MAX_REVIEW_LENGTH = 500
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
