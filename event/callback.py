import chainlit as cl

@cl.action_callback("close_map")
async def on_test_action():
    await cl.ElementSidebar.set_elements([])