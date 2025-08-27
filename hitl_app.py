from llama_index.llms.ollama import Ollama
from llama_index.core.agent.workflow import FunctionAgent, AgentStream
from llama_index.core.workflow import (
    Context, InputRequiredEvent, HumanResponseEvent, JsonSerializer
)    

import chainlit as cl

async def dangerous_task(ctx: Context) -> str:
    """A dangerous task that requires human confirmation."""
    
    question = "Are you sure you want to proceed?"
    response = await ctx.wait_for_event(
        HumanResponseEvent,
        waiter_id=question,
        waiter_event=InputRequiredEvent(
            prefix=question,
            user_name="Titus"
        ),
        requirements={"user_name": "Titus"}
    )
    
    if response.response.strip().lower() == "yes":
        return "Dangerous task completed successfully."
    else:
        return "Dangerous task aborted"

def setup_agent() -> FunctionAgent:
    llm = Ollama(model="qwen2.5", temperature=0)
    
    agent = FunctionAgent(
        llm=llm,
        tools=[dangerous_task],
        system_prompt="You are a helpful assistant that can perform dangerous tasks with human approval."
    )
    
    return agent

@cl.on_chat_start
async def on_chat_start():
    agent = setup_agent()
    ctx = Context(agent)
    cl.user_session.set("last_event", None)
    cl.user_session.set("agent", agent)
    cl.user_session.set("context", ctx.to_dict(serializer=JsonSerializer()))
    cl.user_session.set("input_ev", None)
    
@cl.on_message
async def on_message(message: cl.Message):
    input_ev = cl.user_session.get("input_ev")
    agent = cl.user_session.get("agent")
    ctx_dict = cl.user_session.get("context")
    ctx = Context.from_dict(agent, ctx_dict, serializer=JsonSerializer())
    
    msg = cl.Message(content="")
    
    if input_ev is None:
        handler = agent.run(message.content, ctx=ctx)
        async for event in handler.stream_events():
            if isinstance(event, AgentStream):
                await msg.stream_token(event.delta)
                cl.user_session.set("last_event", "stop_event")
            if isinstance(event, InputRequiredEvent):
                input_ev = event
                cl.user_session.set("context", ctx.to_dict(serializer=JsonSerializer()))
                cl.user_session.set("input_ev", input_ev)
                for chunk in event.prefix.split(" "):
                    await msg.stream_token(chunk)
                msg.content = event.prefix
                cl.user_session.set("last_event", "input_required_event")
                break
        
    
    else: 
        handler = agent.run(ctx=ctx)
        handler.ctx.send_event(
            HumanResponseEvent(
                response=message.content,
                user_name=input_ev.user_name,
            )
        )
        async for event in handler.stream_events():
            if isinstance(event, AgentStream):
                await msg.stream_token(event.delta)
                cl.user_session.set("input_ev", None)
                cl.user_session.set("last_event", "stop_event")
            if isinstance(event, InputRequiredEvent):
                input_ev = event
                cl.user_session.set("context", ctx.to_dict(serializer=JsonSerializer()))
                cl.user_session.set("input_ev", input_ev)
                for chunk in event.prefix.split(" "):
                    await msg.stream_token(chunk)
                msg.content = event.prefix
                cl.user_session.set("last_event", "stop_event")
                break
    
    last_event = cl.user_session.get("last_event")
    if last_event == "stop_event":
        response = await handler
        msg.content = str(response)
        
    await msg.update()
    