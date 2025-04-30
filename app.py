import chainlit as cl
import os
from dotenv import load_dotenv, find_dotenv
from collections import defaultdict
from typing import Optional

from llama_index.core.agent.workflow import FunctionAgent, AgentStream, ToolCall
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.tools import FunctionTool
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.workflow import Context
from llama_index.llms.openai import OpenAI
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec

import logging

logger = logging.getLogger(__name__)

_ = load_dotenv(find_dotenv())

llm = OpenAI("gpt-4o-mini", temperature=0)

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Password auth handler"""
    if (username, password) == ("admin", "admin"):
        return cl.User(identifier="admin", metadata={"role": "ADMIN"})
    else:
        return None

@cl.on_chat_start
async def start():
    """Handler for chat start events. Sets session variables."""
    
    agent_tool = FunctionTool.from_defaults(async_fn=move_map_to)
    cl.user_session.set("agent_tools", [agent_tool])
    cl.user_session.set("mcp_tools", {})
    cl.user_session.set("mcp_tool_cache", defaultdict(list))
    cl.user_session.set(
        "agent",
        FunctionAgent(
            tools=[agent_tool],
            llm=llm,
        )
    )
    memory = ChatMemoryBuffer.from_defaults()
    memory.put(
        ChatMessage(
            role=MessageRole.SYSTEM, 
            content="You are a helpful AI assistant. You can access tools using MCP servers if available."
        )
    )
    cl.user_session.set("memory",memory,)

@cl.on_message
async def on_message(message: cl.Message):
    """On message handler to handle message received events"""
    
    agent = cl.user_session.get("agent")
    memory = cl.user_session.get("memory")
    chat_history = memory.get()
    msg = cl.Message("")
    
    context = cl.user_session.get("context")
    handler = agent.run(
        message.content, 
        chat_history = chat_history,
        ctx = context
    )
    async for event in handler.stream_events():
        if isinstance(event, AgentStream):
            await msg.stream_token(event.delta)
        elif isinstance(event, ToolCall):
            with cl.Step(name=f"{event.tool_name} tool", type="tool"):
                continue
    
    response = await handler
    
    memory.put(
        ChatMessage(
            role = MessageRole.USER,
            content= message.content
        )
    )
    memory.put(
        ChatMessage(
            role = MessageRole.ASSISTANT,
            content = str(response)
        )
    )
    cl.user_session.set("memory", memory)
    
    await msg.send()

@cl.action_callback("close_map")
async def on_test_action():
    """Callback handler to close the map"""
    await cl.ElementSidebar.set_elements([])

@cl.set_starters
async def set_starters():
    """Chat starter suggestions!"""
    return [
        cl.Starter(
            label="Show me Paris",
            message="Show me Paris.",
            icon="/public/paris.png"
        ),
        cl.Starter(
            label="Show me NYC",
            message="Show me NYC.",
            icon="/public/nyc.png"
        ),
        cl.Starter(
            label="Show me Singapore",
            message="Show me Singapore.",
            icon="/public/singapore.png"
        ),
    ]

## MCP Utilities
@cl.on_mcp_connect
async def on_mcp_connect(connection):
    """Handler to connect to an MCP server. 
    Lists tools available on the server and connects these tools to
    the LLM agent."""
    mcp_cache = cl.user_session.get("mcp_tool_cache", {})
    mcp_tools = cl.user_session.get("mcp_tools", {})
    agent_tools = cl.user_session.get("agent_tools", [])
    try:
        logger.info("Connecting to MCP")
        mcp_client = BasicMCPClient(connection.url)
        logger.info("Connected to MCP")
        mcp_tool_spec = McpToolSpec(client=mcp_client)
        logger.info("Unpacking tools")
        new_tools = await mcp_tool_spec.to_tool_list_async()
        for tool in new_tools:
            if tool.metadata.name not in mcp_tools:
                mcp_tools[tool.metadata.name] = tool
                mcp_cache[connection.name].append(tool.metadata.name)
        agent = FunctionAgent(
            tools=agent_tools.extend(list(mcp_tools.values())),
            llm=llm,
        )
        cl.user_session.set("agent", agent)
        cl.user_session.set("context", Context(agent))
        cl.user_session.set("mcp_tools", mcp_tools)
        cl.user_session.set("mcp_tool_cache", mcp_cache)
        await cl.Message(f"Connected to MCP server: {connection.name} on {connection.url}").send()

        await cl.Message(
            f"Found {len(new_tools)} tools from {connection.name} MCP server."
        ).send()
    except Exception as e:
        await cl.Message(f"Error conecting to tools from MCP server: {str(e)}").send()

@cl.on_mcp_disconnect
async def on_mcp_disconnect(name: str):
    """Handler to handle disconnects from an MCP server.
    Updates tool list available for the LLM agent.
    """
    agent_tools = cl.user_session.get("agent_tools", [])
    mcp_tools = cl.user_session.get("mcp_tools", {})
    mcp_cache = cl.user_session.get("mcp_tool_cache", {})
    
    if name in mcp_cache:
        for tool_name in mcp_cache[name]:
            del mcp_tools[tool_name]
        del mcp_cache[name]

    # Update tools list in agent
    if len(mcp_tools)>0:
        agent = FunctionAgent(
            tools=agent_tools.extend(list(mcp_tools.values())), #agent still has tools not removed
            llm=llm,
        )
    else:
        agent = FunctionAgent(
            tools=agent_tools,
            llm=llm,
        )
    cl.user_session.set("context", Context(agent))
    cl.user_session.set("mcp_tools", mcp_tools)
    cl.user_session.set("mcp_tool_cache", mcp_cache)
    cl.user_session.set("agent", agent)
    
    await cl.Message(f"Disconnected from MCP server: {name}").send()

## Map utilities
@cl.step(type="tool")
async def move_map_to(latitude: float, longitude: float):
    """Move the map to the given latitude and longitude."""
    
    await open_map(
        latitude=latitude,
        longitude=longitude
    )

    fn = cl.CopilotFunction(
        name="move-map", args={"latitude": latitude, "longitude": longitude}
    )
    await fn.acall()

    return "Map moved!"

async def open_map(
    latitude: float = 1.290270, 
    longitude: float = 103.851959
):
    map_props = {"latitude": latitude, "longitude": longitude, "zoom": 12}
    custom_element = cl.CustomElement(name="Map", props=map_props, display="inline")
    await cl.ElementSidebar.set_title("canvas")
    await cl.ElementSidebar.set_elements([custom_element], key="map-canvas")