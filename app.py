import chainlit as cl
import litellm
from config.settings import openai_llm, mistral_llm
from config.profiles import chat_profile
from auth.auth import auth_callback

# @cl.set_chat_profiles
# async def chat_profile(current_user: cl.User):
#     if current_user.metadata["role"] != "ADMIN":
#         return None
        
#     return [
#         cl.ChatProfile(
#             name="OpenAI",
#             markdown_description="The underlying LLM model is **gpt-4o-mini**.",
#         ),
#         cl.ChatProfile(
#             name="Mistral",
#             markdown_description="The underlying LLM model is **mistral-small-latest**.",
#             icon="https://picsum.photos/250",
#         ),
#         cl.ChatProfile(
#             name="Gemini",
#             markdown_description="The underlying LLM model is **gemini-2.0-flash**.",
#             icon="https://picsum.photos/200",
#         ),
#     ]

@cl.on_chat_start
async def on_chat_start():
    chat_profile = cl.user_session.get("chat_profile")
    cl.user_session.set("chat_history", [])
    await cl.Message(
        content=f"starting chat using the {chat_profile} chat profile"
    ).send()
    
@cl.on_message
async def on_message(msg: cl.Message):
    await cl.Message("Hi!").send()