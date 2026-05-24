"""Proposal Generator Tool - generates business proposals."""
from app.tools.base import BaseTool


class ProposalGeneratorTool(BaseTool):
    name = "proposal_generator"
    description = "Generate a professional business proposal with pricing and scope."
    input_schema = {
        "type": "object",
        "properties": {
            "client_name": {"type": "string", "description": "Client or company name"},
            "service_type": {"type": "string", "description": "Type of service being proposed"},
            "scope": {"type": "string", "description": "Scope of work description"},
            "budget_range": {"type": "string", "description": "Expected budget range"}
        },
        "required": ["client_name", "service_type"]
    }

    async def execute(self, input_data):
        client = input_data.get("client_name", "")
        service = input_data.get("service_type", "")
        scope = input_data.get("scope", "")
        budget = input_data.get("budget_range", "")
        
        return {
            "success": True,
            "data": {
                "client_name": client,
                "service_type": service,
                "proposal": {
                    "title": f"Proposal for {service} Services",
                    "scope": scope or "To be defined based on client needs",
                    "deliverables": [
                        "Initial consultation and requirements gathering",
                        "Strategy document and timeline",
                        "Implementation and execution",
                        "Reporting and optimization"
                    ],
                    "budget": budget or "Competitive pricing based on scope",
                    "next_steps": "Schedule a detailed requirements call"
                }
            }
        }
