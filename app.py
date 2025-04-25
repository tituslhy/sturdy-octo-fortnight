import os
from dotenv import load_dotenv, find_dotenv

import chainlit as cl
import litellm
from config.settings import openai_llm
from config.profiles import chat_profile
from connection.mcp_handler import (
    on_mcp_connect,
    on_mcp_disconnect
)
from auth.auth_handler import auth_callback

_ = load_dotenv(find_dotenv())

@cl.on_chat_start
async def on_chat_start():
    chat_profile = cl.user_session.get("chat_profile")
    if chat_profile == "OpenAI":
        cl.user_session.set("llm", openai_llm)
    elif chat_profile == "Mistral":
        cl.user_session.set(
            "llm",
            "mistral-small-latest"   
        )
    else:
        cl.user_session.set(
            "llm",
            "gemini-2.0-flash"
        )
    cl.user_session.set("chat_history", [])
    
@cl.on_message
async def on_message(msg: cl.Message):
    await cl.Message("Hi!").send()

## Tool use:
## Map tool and Jira tool