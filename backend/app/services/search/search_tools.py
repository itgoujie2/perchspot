"""
Search Tool Definitions - for Claude to use in chat
"""

GET_RECOMMENDATIONS_TOOL = {
    "name": "get_property_recommendations",
    "description": "Get property recommendations based on homes the user has previously analyzed. Returns similar homes that were found during past property analyses. Use when user asks for suggestions, recommendations, or similar homes to look at.",
    "input_schema": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum number of recommendations to return (default 5)",
                "default": 5
            }
        }
    }
}

ANALYZE_PROPERTY_TOOL = {
    "name": "analyze_property",
    "description": "Run a full analysis on a property address. Use when the user wants to analyze a specific property.",
    "input_schema": {
        "type": "object",
        "properties": {
            "address": {
                "type": "string",
                "description": "The full property address to analyze"
            }
        },
        "required": ["address"]
    }
}
