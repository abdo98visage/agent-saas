"""Tool registry - maps tool names to tool instances."""

from app.tools.web_search import WebSearchTool
from app.tools.competitor_analyzer import CompetitorAnalyzerTool
from app.tools.ad_copy_generator import AdCopyGeneratorTool
from app.tools.crm_lead_saver import CRMLeadSaverTool
from app.tools.proposal_generator import ProposalGeneratorTool


# Global tool registry
# Add new tools here - agents reference them by key name
TOOLS = {
    "web_search": WebSearchTool(),
    "competitor_analyzer": CompetitorAnalyzerTool(),
    "ad_copy_generator": AdCopyGeneratorTool(),
    "crm_lead_saver": CRMLeadSaverTool(),
    "proposal_generator": ProposalGeneratorTool(),
}


def get_tool(tool_name: str):
    """Get a tool by name."""
    return TOOLS.get(tool_name)


def get_tools(tool_names: list):
    """Get multiple tools by names."""
    return [get_tool(name) for name in tool_names if get_tool(name)]
