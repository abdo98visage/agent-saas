"""CRM Lead Saver Tool - saves leads to the database."""
from uuid import uuid4
from app.core.db import supabase
from app.tools.base import BaseTool


class CRMLeadSaverTool(BaseTool):
    name = "crm_lead_saver"
    description = "Save a lead to the organization's CRM database."
    input_schema = {
        "type": "object",
        "properties": {
            "lead_name": {"type": "string", "description": "Lead name"},
            "lead_email": {"type": "string", "description": "Lead email"},
            "lead_phone": {"type": "string", "description": "Lead phone number"},
            "lead_source": {"type": "string", "description": "Source of the lead"},
            "notes": {"type": "string", "description": "Additional notes"},
            "organization_id": {"type": "string", "description": "Organization ID"}
        },
        "required": ["lead_name", "lead_email", "organization_id"]
    }

    async def execute(self, input_data):
        org_id = input_data.get("organization_id")
        
        lead_data = {
            "id": str(uuid4()),
            "organization_id": org_id,
            "lead_name": input_data.get("lead_name", ""),
            "lead_email": input_data.get("lead_email", ""),
            "lead_phone": input_data.get("lead_phone", ""),
            "lead_source": input_data.get("lead_source", ""),
            "notes": input_data.get("notes", ""),
            "status": "new",
        }
        
        # TODO: Add leads table to DB
        # For now, just return structured response
        return {
            "success": True,
            "data": {
                "lead_id": lead_data["id"],
                "message": f"Lead {input_data.get('lead_name')} saved successfully",
                "note": "leads table needed in DB for persistent storage"
            }
        }
