import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

logger = logging.getLogger(__name__)

class BaseTool(ABC):
    """
    Abstract Base Class for all tools.
    Provides a standardized interface, error handling, and logging.
    """
    
    @property
    @abstractmethod
    def tool_name(self) -> str:
        """Name of the tool."""
        pass

    @property
    def mock_mode(self) -> bool:
        """
        Subclasses can override this or we can wire it up to a global config.
        Defaulting to False.
        """
        from app.core.config import settings
        return getattr(settings, "MOCK_MODE", False)

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        The main logic for the tool.
        Must return a standardized dictionary format.
        """
        pass

    async def mock_execute(self, **kwargs) -> Dict[str, Any]:
        """
        Returns mock data when the tool is run in mock mode.
        Default implementation returns a generic success format. Subclasses should override.
        """
        return self._format_response(
            success=True,
            data={"mock": True, "kwargs_received": kwargs},
            message=f"Mock execution successful for {self.tool_name}"
        )

    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        The method that should actually be called by the bots.
        It handles standardizing the output, catching errors, logging, and checking mock mode.
        """
        try:
            self.log_action("run_started", params=kwargs, result=None)
            
            if self.mock_mode:
                result = await self.mock_execute(**kwargs)
            else:
                result = await self.execute(**kwargs)
            
            self.log_action("run_completed", params=kwargs, result=result)
            return result
        except Exception as e:
            return self.handle_error(e)

    def log_action(self, action: str, params: Dict[str, Any], result: Dict[str, Any] = None) -> None:
        """
        Log the tool usage.
        Can be wired up to a database log table later.
        """
        log_data = {
            "tool_name": self.tool_name,
            "action": action,
            "params": params,
            "result": result
        }
        if action == "error":
            logger.error(f"Tool Error [{self.tool_name}]: {log_data}")
        else:
            logger.info(f"Tool Action [{self.tool_name}]: {log_data}")

    def handle_error(self, error: Exception) -> Dict[str, Any]:
        """
        Standard error response generator.
        """
        self.log_action("error", params={}, result={"error_message": str(error)})
        return self._format_response(
            success=False,
            data=None,
            message="An unexpected error occurred while executing the tool.",
            error_details=str(error)
        )
        
    def _format_response(self, success: bool, data: Any = None, message: str = "", error_details: Any = None) -> Dict[str, Any]:
        """Standardized output format for all tools."""
        return {
            "success": success,
            "data": data or {},
            "message": message,
            "error": error_details
        }
