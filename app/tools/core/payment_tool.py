import uuid
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Payment
from app.tools.base_tool import BaseTool

class PaymentTool(BaseTool):
    """
    Core Infrastructure Tool: Payments
    Connects to Razorpay to generate dynamic payment links over WhatsApp.
    Currently in MOCK_MODE for development without API keys.
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    @property
    def tool_name(self) -> str:
        return "PaymentTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Main dispatcher.
        """
        method_name = kwargs.pop("method", None)
        if not method_name:
            return self._format_response(success=False, message="Missing 'method' parameter.")
            
        if method_name == "create_payment_link":
            return await self.create_payment_link(**kwargs)
        elif method_name == "create_subscription":
            return await self.create_subscription(**kwargs)
        elif method_name == "check_payment_status":
            return await self.check_payment_status(**kwargs)
        else:
            return self._format_response(success=False, message=f"Unknown method '{method_name}'")

    async def mock_execute(self, **kwargs) -> Dict[str, Any]:
        """
        Generates functional MOCK data allowing the rest of the bot to be built
        and tested without hitting actual Razorpay APIs or requiring real credit cards.
        """
        method_name = kwargs.get("method")
        
        if method_name == "create_payment_link":
            amt_paise = kwargs.get("amount_paise", 0)
            mock_id = f"plink_mock_{uuid.uuid4().hex[:8]}"
            mock_url = f"https://rzp.io/i/{mock_id}"
            
            # We STILL save the mock payment into the real database so other tools can read it
            new_payment = Payment(
                user_id=kwargs.get("business_id"),
                customer_phone=kwargs.get("customer_phone"),
                amount_paise=amt_paise,
                description=kwargs.get("description", "Mock Payment"),
                razorpay_link_id=mock_id,
                booking_id=kwargs.get("booking_id"),
                status="created"
            )
            self.db.add(new_payment)
            try:
                await self.db.commit()
            except Exception as e:
                await self.db.rollback()
                return self.handle_error(e)
                
            return self._format_response(
                success=True,
                data={
                    "payment_link_id": mock_id,
                    "payment_url": mock_url,
                    "amount_inr": amt_paise / 100
                },
                message=f"Mock Payment Link generated for ₹{amt_paise/100:.2f}."
            )
            
        elif method_name == "check_payment_status":
            # In mock mode, we assume they paid successfully 10 seconds later
            return self._format_response(
                success=True,
                data={"status": "paid", "payment_id": f"pay_mock_{uuid.uuid4().hex[:8]}"},
                message="Mock status is PAID."
            )
            
        return await super().mock_execute(**kwargs)

    async def create_payment_link(self, business_id: str, customer_phone: str, amount_paise: int, 
                                  description: str, booking_id: str = None) -> Dict[str, Any]:
        """
        Creates a real Razorpay link.
        """
        from app.core.config import settings
        
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return self._format_response(success=False, message="Razorpay keys not configured.")
            
        try:
            import razorpay
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            # Razorpay API call
            data = {
                "amount": amount_paise,
                "currency": "INR",
                "accept_partial": False,
                "description": description,
                "customer": {
                    "contact": customer_phone
                },
                "notify": {"sms": False, "email": False}, # We'll send it via WhatsApp ourselves
                "reminder_enable": True
            }
            res = await asyncio.to_thread(client.payment_link.create, data)
            
            # Save to database
            new_payment = Payment(
                user_id=business_id,
                customer_phone=customer_phone,
                amount_paise=amount_paise,
                description=description,
                razorpay_link_id=res["id"],
                booking_id=booking_id,
                status="created"
            )
            self.db.add(new_payment)
            await self.db.commit()
            
            return self._format_response(
                success=True,
                data={"payment_link_id": res["id"], "payment_url": res["short_url"]},
                message="Payment link generated."
            )
            
        except ImportError:
            return self._format_response(success=False, message="'razorpay' package not installed. Run 'pip install razorpay'.")
        except Exception as e:
            return self.handle_error(e)

    async def check_payment_status(self, payment_link_id: str) -> Dict[str, Any]:
        """Queries Razorpay API for status."""
        from app.core.config import settings
        # To be implemented when moving out of MOCK mode
        return self._format_response(success=False, message="Not implemented.")

    async def create_subscription(self, **kwargs) -> Dict[str, Any]:
        """Creates Razorpay recurring subscription."""
        return self._format_response(success=False, message="Not implemented.")
