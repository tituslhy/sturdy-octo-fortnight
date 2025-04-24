from dotenv import load_dotenv, find_dotenv
from openai import AsyncOpenAI

_ = load_dotenv(find_dotenv())
llm = AsyncOpenAI()