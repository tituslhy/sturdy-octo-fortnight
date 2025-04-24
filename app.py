import chainlit as cl
import litellm
from config.settings import openai_llm, mistral_llm

@cl.on_chat_start
async def on_start():
    cl.user_session.set("chat_messages", [])
    
@cl.on_message
async def on_message(msg: cl.Message):
    await cl.Message("Hi!").send()