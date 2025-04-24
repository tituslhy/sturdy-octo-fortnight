# from llama_index.llms.openai import OpenAI
from openai import AsyncOpenAI

llm = AsyncOpenAI(model="gpt-4o-mini", temperature=0)