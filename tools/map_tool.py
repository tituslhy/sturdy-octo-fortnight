tools = [
    {
        "name": "move_map_to",
        "description": "Move the map to the given latitude and longitude.",
        "input_schema": {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "string",
                    "description": "The latitude of the location to move the map to",
                },
                "longitude": {
                    "type": "string",
                    "description": "The longitude of the location to move the map to",
                },
            },
            "required": ["latitude", "longitude"],
        },
    }
]