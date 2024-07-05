import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

HOST = os.getenv("HOST", "localhost")
PORT = int(os.getenv("PORT", 8000))