from dotenv import load_dotenv

load_dotenv(".env")

OPENAI_API_KEY = "sk-proj-abc1234567890abcdef1234567890abcdef"


def get_key():
    return OPENAI_API_KEY
