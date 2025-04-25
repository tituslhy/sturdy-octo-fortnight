import chainlit as cl
import litellm
from config.settings import openai_llm, mistral_llm
from config.profiles import chat_profile
from connection.mcp_handler 
from auth.auth_handler import auth_callback

@cl.on_chat_start
async def on_chat_start():
    chat_profile = cl.user_session.get("chat_profile")
    cl.user_session.set("chat_history", [])
    
@cl.on_message
async def on_message(msg: cl.Message):
    await cl.Message("Hi!").send()