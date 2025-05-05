import chainlit as cl
from llama_index.llms.openai import OpenAI

llm = OpenAI('gpt-4o-mini', temperature=0)

@cl.on_message
async def on_message(message: cl.Message):
    reply = await llm.acomplete(message.content)
    response = await cl.Message(content=str(reply)).send()
    
    if cl.context.session.client_type == "copilot":
        fn = cl.CopilotFunction(
            name="test",
            args={"message": message.content, "response": response.content}
        )
        await fn.acall()