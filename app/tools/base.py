from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseTool(ABC):
    """Unified tool interface - all agent tools inherit from this."""
    
    name: str
    description: str
    input_schema: Dict = {}

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool and return result."""
        pass


class ToolResult:
    """Standardized tool result."""
    
    def __init__(
        self,
        success: bool,
        data: Any = None,
        error: Optional[str] = None,
        latency_ms: Optional[int] = None,
    ):
        self.success = success
        self.data = data
        self.error = error
        self.latency_ms = latency_ms

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }
