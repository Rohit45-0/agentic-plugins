import logging
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class CommandParser:
    """
    Parses structural owner-commands to bypass language models.
    """
    
    @staticmethod
    def parse(message: str) -> dict:
        msg = message.lower().strip()
        
        if msg.startswith("walkin"):
            parts = msg.split()
            time = parts[1] if len(parts) > 1 else None
            count = parts[2] if len(parts) > 2 else "1"
            return {"command": "walkin", "time": time, "count": count}
            
        if msg.startswith("off"):
            return {"command": "off", "details": msg[3:].strip()}
            
        if msg in ["summary", "aaj ka hisaab"]:
            return {"command": "summary"}
            
        if msg in ["menu update", "menu badlo"]:
            return {"command": "menu_update"}
            
        if msg.startswith("holiday"):
            return {"command": "holiday", "date": msg[7:].strip()}
            
        if msg.startswith("cancel"):
            return {"command": "cancel", "target": msg[6:].strip()}
            
        if msg.startswith("staff off"):
            # staff off rahul 15 march
            parts = msg[9:].strip().split()
            staff_name = parts[0] if len(parts) > 0 else None
            date_str = " ".join(parts[1:]) if len(parts) > 1 else None
            return {"command": "staff_off", "staff_name": staff_name, "date": date_str}
            
        return None

class BaseBot(ABC):
    """
    Abstract framework for all Vertical Bots.
    """
    def __init__(self, db: Session, business, owner, config):
        self.db = db
        self.business = business
        self.owner = owner
        self.config = config

    @abstractmethod
    async def handle_customer_message(self, customer, session_id: str, message_text: str, message_obj: dict) -> str:
        """
        Processes standard customer interactions using RAG or specialized Vertical Logic.
        """
        pass

    @abstractmethod
    async def process_owner_command(self, command_dict: dict, raw_message: str) -> str:
        """
        Executes explicit structural instructions from the business owner.
        """
        pass

    async def run(self, is_owner: bool, customer_or_owner, session_id: str, message_text: str, message_obj: dict) -> str:
        """
        Main entry point for handling an incoming chat message.
        """
        try:
            if is_owner:
                cmd = CommandParser.parse(message_text)
                if cmd:
                    logger.info(f"Executing explicit owner command: {cmd['command']}")
                    return await self.process_owner_command(cmd, message_text)
                else:
                    return await self._fallback_owner_handler(customer_or_owner, message_text, message_obj)
            else:
                return await self.handle_customer_message(customer_or_owner, session_id, message_text, message_obj)
        except Exception as e:
            logger.error(f"Error executing bot: {e}")
            return f"❌ Encountered an error: {str(e)}"

    async def _fallback_owner_handler(self, owner, text, obj):
        # Can route to RAG generation override or simple addition over here if no physical structural command matches
        return "I received your message but it did not match any of my known structural commands (e.g. `walkin 2pm 1`, `summary`, etc.)."
