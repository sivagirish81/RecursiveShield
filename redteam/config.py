import os
from dotenv import load_dotenv

# Load environment variables from .env file at the root of the project
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY")
MINIMAX_GROUP_ID = os.environ.get("MINIMAX_GROUP_ID")
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")

# Pin defaults based on PROJECT.md/TASK_B
MINIMAX_MODEL_ID = "speech-02-hd"  # Standard default, can override in .env
VOYAGE_MODEL_ID = "voyage-3"       # Standard default, can override in .env
ANTIGRAVITY_AGENT_ID = "antigravity-preview-05-2026"
