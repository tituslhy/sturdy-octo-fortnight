import chainlit as cl
from litellm import acompletion
from openai import AsyncOpenAI

import json
from typing import Dict, Any, Literal, List, Optional, Callable
from dotenv import load_dotenv, find_dotenv

import os
import sys

__curdir__ = os.getcwd()
if "src" in __curdir__:
    sys.path.append("../utils")
    sys.path.append(".")
else:
    sys.path.append("./utils")
    sys.path.append("./src")

from openai_format import format_calltoolresult_content
from map_tool_steps import call_map_tool

_ = load_dotenv(find_dotenv())

openai_client = AsyncOpenAI()

USER_TOOL_FUNCTIONS: Dict[str, Callable[..., Any]] = {}

def register_tool(name: str, func: Callable[..., Any]):
    """Register a custom async tool by name."""
    USER_TOOL_FUNCTIONS[name] = func

# Register your custom tools here
register_tool("move_map_to", call_map_tool)

async def _stream_handler(
    streamer,  # Callable returning async iterator
    model: str,
    messages: List[Dict[str, Any]],
    functions: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Generic streaming + function-calling handler.
    - `streamer` is a callable accepting model, messages, stream, **kwargs
    - Returns updated message history
    """
    msg = cl.Message("")
    await msg.send()

    params: Dict[str, Any] = {"model": model, "messages": messages, "stream": True}
    if functions:
        params.update({"functions": functions, "function_call": "auto"})

    stream = streamer(**params)
    full_resp = ""
    func_calls: List[Dict[str, str]] = []

    async for part in stream:
        delta = part.choices[0].delta
        if content := delta.get("content"):
            full_resp += content
            await msg.stream_token(content)
        if fc := delta.get("function_call"):
            func_calls.append({"name": fc["name"], "arguments": fc["arguments"]})

    await msg.update()

    if full_resp.strip():
        messages.append({"role": "assistant", "content": full_resp})

    for call in func_calls:
        name = call["name"]
        args = json.loads(call["arguments"])
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": f"call_{len(messages)}",
                "type": "function",
                "function": {"name": name, "arguments": call["arguments"]}
            }]
        })
        result = await execute_tool(name, args)
        content = format_calltoolresult_content(result)
        await cl.Message(content=f"🔧 **{name}** returned:\n{content}", author="tool").send()
        messages.append({"role": "tool", "tool_call_id": f"call_{len(messages)-1}", "content": content})
        follow = cl.Message("")
        await follow.send()
        follow_stream = streamer(model=model, messages=messages, stream=True)
        follow_text = ""
        async for chunk in follow_stream:
            if tok := chunk.choices[0].delta.get("content"):
                follow_text += tok
                await follow.stream_token(tok)
        await follow.update()
        messages.append({"role": "assistant", "content": follow_text})

    return messages

# Helper to choose streamer based on model
def _get_streamer(model_name: str):
    # Use LiteLLM for Mistral and Gemini
    if model_name.startswith("mistral") or model_name.startswith("gemini"):
        return lambda **kw: acompletion(**kw)
    # Use OpenAI client for official OpenAI models
    return lambda **kw: openai_client.chat.completions.create(**kw)

@cl.step(type="tool")
async def execute_tool(name: str, tool_input: Dict[str, Any]) -> Any:
    """
    General tool executor. Dispatches to user-defined tools first,
    then falls back to MCP-connected tool servers.
    """
    # Normalize the function name (e.g., 'move-map' -> 'move_map')
    name_key = name.replace('-', '_')

    # 1. Check user-defined tools
    if name_key in USER_TOOL_FUNCTIONS:
        func = USER_TOOL_FUNCTIONS[name_key]
        try:
            return await func(**tool_input)
        except TypeError as e:
            return {"error": f"Invalid input for {name_key}: {e}"}
        except Exception as e:
            return {"error": f"Error executing {name_key}: {e}"}

    # 2. Fallback to MCP server tools
    mcp_tools = cl.user_session.get("mcp_tools", {})
    mcp_name = next(
        (conn for conn, tools in mcp_tools.items() if any(t["name"] == name for t in tools)),
        None
    )
    if not mcp_name:
        return {"error": f"Tool '{name}' not found"}

    mcp_session, _ = cl.context.session.mcp_sessions.get(mcp_name)
    try:
        return await mcp_session.call_tool(name, tool_input)
    except Exception as e:
        return {"error": f"MCP call error for '{name}': {e}"}

@cl.step(type="llm")
async def ask_litellm(
    llm: Literal["mistral-small-latest", "gemini-2.0-flash"],
    functions: Optional[List[Dict[str, Any]]] = None
):
    messages = cl.user_session.get("history", [])
    streamer = _get_streamer(llm)
    updated = await _stream_handler(
        streamer=streamer,
        model=llm,
        messages=messages,
        functions=functions
    )
    cl.user_session.set("history", updated)

@cl.step(type="llm")
async def ask_openai(
    llm: str = "gpt-4o-mini",
    functions: Optional[List[Dict[str, Any]]] = None
):
    messages = cl.user_session.get("history", [])
    streamer = _get_streamer(llm)
    updated = await _stream_handler(
        streamer=streamer,
        model=llm,
        messages=messages,
        functions=functions
    )
    cl.user_session.set("history", updated)