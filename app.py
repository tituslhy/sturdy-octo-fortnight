import chainlit as cl

import os
from dotenv import load_dotenv, find_dotenv
from collections import defaultdict
from typing import Optional

import httpx
import io
import wave
import numpy as np
import audioop

from llama_index.core.agent.workflow import FunctionAgent, AgentStream, ToolCall
from llama_index.core.base.llms.types import ChatMessage, MessageRole
from llama_index.core.tools import FunctionTool
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.workflow import Context
from llama_index.llms.openai import OpenAI
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec

from openai import AsyncOpenAI

import logging

logger = logging.getLogger(__name__)

_ = load_dotenv(find_dotenv())

openai_llm = OpenAI("gpt-4o-mini", temperature=0)
openai_client = AsyncOpenAI() #for whisper

## Audio settings
SILENCE_THRESHOLD = 3500  # Adjust based on your audio level (e.g., lower for quieter audio)
SILENCE_TIMEOUT = 1300.0  # Seconds of silence to consider the turn finished
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Password auth handler for login"""
    
    if (username, password) == ("admin", "admin"):
        return cl.User(identifier="admin", metadata={"role": "ADMIN"})
    else:
        return None

@cl.on_chat_start
async def start():
    """Handler for chat start events. Sets session variables."""
    # await open_map()
    
    agent_tool = FunctionTool.from_defaults(async_fn=move_map_to)
    agent = FunctionAgent(tools=[agent_tool],llm=openai_llm,)
    
    cl.user_session.set("agent_tools", [agent_tool])
    cl.user_session.set("context", Context(agent))
    cl.user_session.set("mcp_tools", {})
    cl.user_session.set("mcp_tool_cache", defaultdict(list))
    cl.user_session.set("agent", agent)
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
    await cl.Message(content="Closed map! 🗺️").send()
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

## Audio handlers
@cl.on_audio_start
async def on_audio_start():
    """Handler to manage mic button click event"""
    
    cl.user_session.set("silent_duration_ms", 0)
    cl.user_session.set("is_speaking", False)
    cl.user_session.set("audio_chunks", [])
    return True

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    """Handller function to manage audio chunks"""
    
    audio_chunks = cl.user_session.get("audio_chunks")

    if audio_chunks is not None:
        audio_chunk = np.frombuffer(chunk.data, dtype=np.int16)
        audio_chunks.append(audio_chunk)

    # If this is the first chunk, initialize timers and state
    if chunk.isStart:
        cl.user_session.set("last_elapsed_time", chunk.elapsedTime)
        cl.user_session.set("is_speaking", True)
        return

    last_elapsed_time = cl.user_session.get("last_elapsed_time")
    silent_duration_ms = cl.user_session.get("silent_duration_ms")
    is_speaking = cl.user_session.get("is_speaking")

    # Calculate the time difference between this chunk and the previous one
    time_diff_ms = chunk.elapsedTime - last_elapsed_time
    cl.user_session.set("last_elapsed_time", chunk.elapsedTime)

    # Compute the RMS (root mean square) energy of the audio chunk
    audio_energy = audioop.rms(
        chunk.data, 2
    )  # Assumes 16-bit audio (2 bytes per sample)

    if audio_energy < SILENCE_THRESHOLD:
        # Audio is considered silent
        silent_duration_ms += time_diff_ms
        cl.user_session.set("silent_duration_ms", silent_duration_ms)
        if silent_duration_ms >= SILENCE_TIMEOUT and is_speaking:
            cl.user_session.set("is_speaking", False)
            await process_audio()
    else:
        # Audio is not silent, reset silence timer and mark as speaking
        cl.user_session.set("silent_duration_ms", 0)
        if not is_speaking:
            cl.user_session.set("is_speaking", True)
    
async def process_audio():
    """ Processes the audio buffer from the session"""
    
    if audio_chunks := cl.user_session.get("audio_chunks"):
        # Concatenate all chunks
        concatenated = np.concatenate(list(audio_chunks))

        # Create an in-memory binary stream
        wav_buffer = io.BytesIO()

        # Create WAV file with proper parameters
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
            wav_file.setframerate(24000)  # sample rate (24kHz PCM)
            wav_file.writeframes(concatenated.tobytes())

        # Reset buffer position
        wav_buffer.seek(0)

        cl.user_session.set("audio_chunks", [])

    frames = wav_file.getnframes()
    rate = wav_file.getframerate()

    duration = frames / float(rate)
    if duration <= 1.71:
        print("The audio is too short, please try again.")
        return

    audio_buffer = wav_buffer.getvalue()

    input_audio_el = cl.Audio(content=audio_buffer, mime="audio/wav")

    whisper_input = ("audio.wav", audio_buffer, "audio/wav")
    transcription = await speech_to_text(whisper_input)

    await cl.Message(
        author="You",
        type="user_message",
        content=transcription,
        elements=[input_audio_el],
    ).send()

    ## Now to answer the question
    agent = cl.user_session.get("agent")
    memory = cl.user_session.get("memory")
    chat_history = memory.get()
    msg = cl.Message("")
    
    context = cl.user_session.get("context")
    handler = agent.run(
        transcription, 
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
    await msg.send()
    memory.put(
        ChatMessage(
            role = MessageRole.USER,
            content= transcription
        )
    )
    memory.put(
        ChatMessage(
            role = MessageRole.ASSISTANT,
            content = str(response)
        )
    )
    cl.user_session.set("memory", memory)

    _, output_audio = await text_to_speech(str(response), "audio/wav")

    output_audio_el = cl.Audio(
        auto_play=True,
        mime="audio/wav",
        content=output_audio,
    )
    msg.elements=[output_audio_el]
    await msg.update()

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
            llm=openai_llm,
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
            llm=openai_llm,
        )
    else:
        agent = FunctionAgent(
            tools=agent_tools,
            llm=openai_llm,
        )
    cl.user_session.set("context", Context(agent))
    cl.user_session.set("mcp_tools", mcp_tools)
    cl.user_session.set("mcp_tool_cache", mcp_cache)
    cl.user_session.set("agent", agent)
    
    await cl.Message(f"Disconnected from MCP server: {name}").send()

## Steps
@cl.step(type="tool")
async def speech_to_text(audio_file):
    response = await openai_client.audio.transcriptions.create(
        model="whisper-1", file=audio_file, language="en",
    )

    return response.text


@cl.step(type="tool")
async def text_to_speech(text: str, mime_type: str):
    CHUNK_SIZE = 1024

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

    headers = {
        "Accept": mime_type,
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }

    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(url, json=data, headers=headers)
        response.raise_for_status()  # Ensure we notice bad responses

        buffer = io.BytesIO()
        buffer.name = f"output_audio.{mime_type.split('/')[1]}"

        async for chunk in response.aiter_bytes(chunk_size=CHUNK_SIZE):
            if chunk:
                buffer.write(chunk)

        buffer.seek(0)
        return buffer.name, buffer.read()
    
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

## Map utilities
async def open_map(
    latitude: float = 1.290270, 
    longitude: float = 103.851959
):
    """Handler function to shift the canvas to a specific longitude and latitude component"""
    
    map_props = {"latitude": latitude, "longitude": longitude, "zoom": 12}
    custom_element = cl.CustomElement(name="Map", props=map_props, display="inline")
    await cl.ElementSidebar.set_title("canvas")
    await cl.ElementSidebar.set_elements([custom_element], key="map-canvas")