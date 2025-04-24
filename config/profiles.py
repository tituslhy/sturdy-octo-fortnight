import chainlit as cl

@cl.set_chat_profiles
async def chat_profile(current_user: cl.User):
    if current_user.metadata["role"] != "ADMIN":
        return None

    return [
        cl.ChatProfile(
            name="OpenAI",
            markdown_description="The underlying LLM model is **gpt-4o-mini**.",
        ),
        cl.ChatProfile(
            name="Mistral",
            markdown_description="The underlying LLM model is **mistral-small-latest**.",
            icon="https://picsum.photos/250",
        ),
        cl.ChatProfile(
            name="Gemini",
            markdown_description="The underlying LLM model is **gemini-2.0-flash**.",
            icon="https://picsum.photos/200",
        ),
    ]
