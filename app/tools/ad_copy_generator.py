"""Ad Copy Generator Tool - generates marketing ad copy."""
from app.tools.base import BaseTool


class AdCopyGeneratorTool(BaseTool):
    name = "ad_copy_generator"
    description = "Generate compelling ad copy for Google Ads, Facebook Ads, or other platforms."
    input_schema = {
        "type": "object",
        "properties": {
            "product": {"type": "string", "description": "Product or service being advertised"},
            "platform": {"type": "string", "description": "Ad platform: google, facebook, instagram, tiktok"},
            "target_audience": {"type": "string", "description": "Target audience description"},
            "tone": {"type": "string", "description": "Tone of voice: professional, casual, urgent, friendly"}
        },
        "required": ["product", "platform"]
    }

    async def execute(self, input_data):
        product = input_data.get("product", "")
        platform = input_data.get("platform", "google")
        audience = input_data.get("target_audience", "general")
        tone = input_data.get("tone", "professional")
        
        return {
            "success": True,
            "data": {
                "product": product,
                "platform": platform,
                "target_audience": audience,
                "tone": tone,
                "ad_copies": [
                    f"Headline 1: Transform Your Business with {product}",
                    f"Headline 2: The Smart Choice for {audience}",
                    f"Description: Discover how {product} helps {audience} achieve their goals. Trusted by industry leaders."
                ]
            }
        }
