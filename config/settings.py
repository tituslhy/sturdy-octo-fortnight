from dotenv import load_dotenv, find_dotenv
from openai import AsyncOpenAI
from mistralai import Mistral

_ = load_dotenv(find_dotenv())

openai_llm = AsyncOpenAI()
mistral_llm = Mistral()