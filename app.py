import os
from dotenv import load_dotenv, find_dotenv

import chainlit as cl
from config.profiles import chat_profile
from connection.mcp_handler import (
    on_mcp_connect,
    on_mcp_disconnect
)
from auth.auth_handler import auth_callback
from src.chat_tool_steps import (
    execute_tool,
    ask_litellm,
    ask_openai
)
from src.map_tool_steps import move_map_to
from src.mcp_tool_steps import execute_mcp_tool

_ = load_dotenv(find_dotenv())

@cl.on_chat_start
async def on_chat_start():
    chat_profile = cl.user_session.get("chat_profile")
    if chat_profile == "OpenAI":
        cl.user_session.set("llm", "gpt-4o-mini")
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