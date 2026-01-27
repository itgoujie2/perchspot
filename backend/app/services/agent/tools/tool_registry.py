"""
Tool Registry for managing and discovering granular analysis tools.
"""

import logging
from typing import Dict, List, Type, Optional
from .base_tool import BaseTool

# Import all implemented tools
from .education import AnalyzeSchoolQuality
from .neighborhood import AnalyzeCrimeRisk
from .investment import CalculateInvestmentMetrics
from .location_commute import AnalyzeWalkability
from .property import AssessPropertyQuality

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for all granular analysis tools.

    Responsibilities:
    - Register and discover available tools
    - Organize tools by category
    - Provide tool lookup by name or category
    - Instantiate tools on demand
    """

    def __init__(self):
        self._tools: Dict[str, Type[BaseTool]] = {}
        self._tools_by_category: Dict[str, List[str]] = {
            "property_quality": [],
            "location_commute": [],
            "neighborhood": [],
            "education": [],
            "environmental": [],
            "investment": []
        }

        # Register all available tools
        self._register_default_tools()

    def _register_default_tools(self):
        """Register all implemented tools."""

        # Property Quality tools
        self.register_tool("assess_property_quality", AssessPropertyQuality, "property_quality")

        # Education tools
        self.register_tool("analyze_school_quality", AnalyzeSchoolQuality, "education")

        # Neighborhood tools
        self.register_tool("analyze_crime_risk", AnalyzeCrimeRisk, "neighborhood")

        # Investment tools
        self.register_tool("calculate_investment_metrics", CalculateInvestmentMetrics, "investment")

        # Location/Commute tools
        self.register_tool("analyze_walkability", AnalyzeWalkability, "location_commute")

        logger.info(f"Registered {len(self._tools)} analysis tools across {len(self._tools_by_category)} categories")

    def register_tool(self, tool_name: str, tool_class: Type[BaseTool], category: str):
        """
        Register a tool in the registry.

        Args:
            tool_name: Unique identifier for the tool
            tool_class: Tool class (must inherit from BaseTool)
            category: Category name (property_quality, education, etc.)
        """
        if not issubclass(tool_class, BaseTool):
            raise ValueError(f"Tool {tool_name} must inherit from BaseTool")

        if category not in self._tools_by_category:
            self._tools_by_category[category] = []

        self._tools[tool_name] = tool_class
        self._tools_by_category[category].append(tool_name)

        logger.debug(f"Registered tool: {tool_name} in category: {category}")

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Get an instance of a tool by name.

        Args:
            tool_name: Name of the tool to instantiate

        Returns:
            Instantiated tool or None if not found
        """
        tool_class = self._tools.get(tool_name)
        if tool_class:
            return tool_class()
        else:
            logger.warning(f"Tool not found: {tool_name}")
            return None

    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """
        Get all tools in a specific category.

        Args:
            category: Category name

        Returns:
            List of instantiated tools in the category
        """
        tool_names = self._tools_by_category.get(category, [])
        tools = []

        for tool_name in tool_names:
            tool = self.get_tool(tool_name)
            if tool:
                tools.append(tool)

        return tools

    def get_all_tools(self) -> Dict[str, BaseTool]:
        """
        Get all registered tools.

        Returns:
            Dictionary mapping tool names to instantiated tools
        """
        return {name: tool_class() for name, tool_class in self._tools.items()}

    def list_tool_names(self, category: Optional[str] = None) -> List[str]:
        """
        List all registered tool names, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of tool names
        """
        if category:
            return self._tools_by_category.get(category, [])
        else:
            return list(self._tools.keys())

    def get_categories(self) -> List[str]:
        """Get list of all categories."""
        return list(self._tools_by_category.keys())

    def get_category_summary(self) -> Dict[str, int]:
        """
        Get summary of tools per category.

        Returns:
            Dictionary mapping category to tool count
        """
        return {
            category: len(tools)
            for category, tools in self._tools_by_category.items()
        }


# Global registry instance
_registry = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry instance (singleton)."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
