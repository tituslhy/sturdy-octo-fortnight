import chainlit as cl

import json

## Map tool
@cl.step(type="tool")
async def move_map_to(latitude: float, longitude: float):
    await open_map()

    fn = cl.CopilotFunction(
        name="move-map", args={"latitude": latitude, "longitude": longitude}
    )
    await fn.acall()

    return "Map moved!"

TOOL_FUNCTIONS = {"move_map_to": move_map_to,}

async def open_map():
    map_props = {"latitude": 37.7749, "longitude": -122.4194, "zoom": 12}
    custom_element = cl.CustomElement(name="Map", props=map_props, display="inline")
    await cl.ElementSidebar.set_title("canvas")
    await cl.ElementSidebar.set_elements([custom_element], key="map-canvas")

async def call_map_tool(tool_use):
    tool_name = tool_use.name
    tool_input = tool_use.input

    tool_function = TOOL_FUNCTIONS.get(tool_name)

    if tool_function:
        try:
            return await tool_function(**tool_input)
        except TypeError:
            return json.dumps({"error": f"Invalid input for {tool_name}"})
    else:
        return json.dumps({"error": f"Invalid tool: {tool_name}"})