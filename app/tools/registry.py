"""
Tool Registry
==============
Maps use_case_type → OpenAI function definitions + executor callables.
The WhatsApp handler calls `get_tools_for_vertical(use_case)` to get the
function schemas, and `execute_tool(use_case, function_name, args)` to run them.

This is the BRIDGE between the GPT agent and our Python tool classes.
"""
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  OpenAI Function Schemas — one per tool method the AI can call
# ═══════════════════════════════════════════════════════════════════════════

# ──── Shared / Cross-Vertical Tools ────────────────────────────────────────

_WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "check_weather_and_suggest",
        "description": "Check the current weather in the city and suggest rain-day or cold-day promotions to push to customers.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name (default: Pune)"}
            },
            "required": []
        }
    }
}

_DISTANCE_TOOL = {
    "type": "function",
    "function": {
        "name": "check_delivery_distance",
        "description": "Calculate how far a delivery address is from the shop and estimate delivery charges.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {"type": "string", "description": "Customer's delivery address or area name."},
                "origin": {"type": "string", "description": "Shop/business address. Optional - uses default if not provided."}
            },
            "required": ["destination"]
        }
    }
}

# ──── Restaurant Tools ─────────────────────────────────────────────────────

_RESTAURANT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_menu",
            "description": "Get the full restaurant menu with prices and availability. Use this when customer asks about the menu, items, or prices.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_item_availability",
            "description": "Check if a specific menu item is available right now.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Name of the food item to check."}
                },
                "required": ["item_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_order",
            "description": "Place a new order for a customer. Use this after confirming items and quantities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {"type": "string", "description": "Comma-separated list of items ordered (e.g. '2x Paneer Tikka, 1x Dal Makhani')."},
                    "total_amount": {"type": "string", "description": "Total bill amount in rupees."},
                    "delivery_address": {"type": "string", "description": "Delivery address. Use 'Dine-in' for eat-in orders."}
                },
                "required": ["items", "total_amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_history",
            "description": "Get the customer's past orders so they can easily reorder. Use when customer says 'same as last time' or asks about past orders.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    _WEATHER_TOOL,
    _DISTANCE_TOOL,
]

# ──── Tiffin Tools ─────────────────────────────────────────────────────────

_TIFFIN_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_todays_menu",
            "description": "Get today's tiffin menu (lunch and dinner). Use when customer asks 'aaj ka menu kya hai?'",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_subscription",
            "description": "Start a new tiffin subscription for the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_type": {
                        "type": "string",
                        "enum": ["daily_lunch", "daily_dinner", "both", "weekly"],
                        "description": "Subscription plan type."
                    },
                    "delivery_address": {"type": "string", "description": "Customer's delivery address."}
                },
                "required": ["plan_type", "delivery_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pause_subscription",
            "description": "Pause tiffin delivery for a date range (e.g. when customer is travelling).",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_date": {"type": "string", "description": "Start date of pause (YYYY-MM-DD)."},
                    "to_date": {"type": "string", "description": "End date of pause (YYYY-MM-DD)."}
                },
                "required": ["from_date", "to_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resume_subscription",
            "description": "Resume a paused tiffin subscription.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    _DISTANCE_TOOL,
]

# ──── Salon Tools ──────────────────────────────────────────────────────────

_SALON_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_salon_slots",
            "description": "Check available appointment slots for a specific date and optionally a preferred staff member.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_type": {"type": "string", "description": "Type of service (e.g. Haircut, Facial, Spa)."},
                    "preferred_date": {"type": "string", "description": "Preferred date in YYYY-MM-DD format."},
                    "preferred_staff": {"type": "string", "description": "Preferred stylist/staff member name (optional)."}
                },
                "required": ["service_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_salon_appointment",
            "description": "Book a salon appointment for the customer after they confirm a slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service to book (e.g. Haircut, Facial)."},
                    "staff": {"type": "string", "description": "Staff member name."},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
                    "time": {"type": "string", "description": "Time in HH:MM format."}
                },
                "required": ["service", "staff", "date", "time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_loyalty_status",
            "description": "Check the customer's loyalty tier, visit count, and next reward milestone.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]

# ──── Clinic Tools ─────────────────────────────────────────────────────────

_CLINIC_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_token",
            "description": "Generate a queue token for the patient and tell them their estimated wait time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Reason for visit (e.g. 'fever', 'check-up', 'follow-up')."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_queue_status",
            "description": "Check the current queue length and which token number is being served.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]

# ──── Kirana Tools ─────────────────────────────────────────────────────────

_KIRANA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Search for a product in the store inventory by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Product name to search for (e.g. 'atta', 'sugar', 'maggi')."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_udhar_balance",
            "description": "Check the customer's current credit (udhar/khata) balance.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    _DISTANCE_TOOL,
]

# ──── Coaching Tools ───────────────────────────────────────────────────────

_COACHING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_attendance_report",
            "description": "Get the student's attendance percentage for the current or specified month.",
            "parameters": {
                "type": "object",
                "properties": {
                    "month": {"type": "string", "description": "Month in YYYY-MM format (optional, defaults to current month)."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_fees",
            "description": "Check if the student has any unpaid fee invoices.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
]

# ──── Gym Tools ────────────────────────────────────────────────────────────

_GYM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_membership",
            "description": "Check the customer's gym membership status, days remaining, and current streak.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_class_schedule",
            "description": "Get the upcoming gym/yoga class schedule with availability.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_class",
            "description": "Book a spot in a specific class. Adds to waitlist if full.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class_date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
                    "class_time": {"type": "string", "description": "Time in HH:MM format."}
                },
                "required": ["class_date", "class_time"]
            }
        }
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  Registry Map
# ═══════════════════════════════════════════════════════════════════════════

VERTICAL_TOOLS: Dict[str, List[dict]] = {
    "restaurant": _RESTAURANT_TOOLS,
    "tiffin": _TIFFIN_TOOLS,
    "salon": _SALON_TOOLS,
    "clinic": _CLINIC_TOOLS,
    "kirana": _KIRANA_TOOLS,
    "coaching": _COACHING_TOOLS,
    "gym": _GYM_TOOLS,
    "general": [],  # General uses only core calendar tools
}


def get_tools_for_vertical(use_case_type: str) -> List[dict]:
    """
    Returns the OpenAI function schemas for a given vertical.
    These get appended to the standard calendar tools in the WhatsApp handler.
    """
    return VERTICAL_TOOLS.get(use_case_type, [])


# ═══════════════════════════════════════════════════════════════════════════
#  Tool Executor — Bridges function_name → actual Python tool execution
# ═══════════════════════════════════════════════════════════════════════════

async def execute_vertical_tool(
    use_case_type: str,
    function_name: str,
    function_args: Dict[str, Any],
    customer_phone: str,
    customer_name: str = "Customer",
    spreadsheet_id: Optional[str] = None,
    business_name: str = "Business",
) -> str:
    """
    Routes a function call from the LLM to the correct Python tool and returns the result as a string.
    This is the core execution bridge.
    """
    try:
        # Use a placeholder spreadsheet ID if none configured
        sheet_id = spreadsheet_id or "NOT_CONFIGURED"

        # ── Restaurant ─────────────────────────────────────────────
        if function_name == "get_menu":
            from app.tools.vertical.restaurant_tools import MenuTool
            tool = MenuTool()
            result = await tool.run(method="get_menu_for_display", spreadsheet_id=sheet_id)
            return result["data"].get("menu_message", result["message"]) if result["success"] else result["message"]

        elif function_name == "check_item_availability":
            from app.tools.vertical.restaurant_tools import MenuTool
            tool = MenuTool()
            result = await tool.run(method="check_item_availability", spreadsheet_id=sheet_id, item_name=function_args["item_name"])
            return result["message"]

        elif function_name == "create_order":
            from app.tools.vertical.restaurant_tools import OrderTool
            tool = OrderTool()
            result = await tool.run(
                method="create_order",
                spreadsheet_id=sheet_id,
                customer_phone=customer_phone,
                customer_name=customer_name,
                items=function_args.get("items", ""),
                total_amount=function_args.get("total_amount", "0"),
                delivery_address=function_args.get("delivery_address", "Dine-in"),
            )
            return result["message"]

        elif function_name == "get_order_history":
            from app.tools.vertical.restaurant_tools import OrderTool
            tool = OrderTool()
            result = await tool.run(method="get_order_history", spreadsheet_id=sheet_id, customer_phone=customer_phone)
            if result["success"] and result["data"].get("orders"):
                orders = result["data"]["orders"]
                msg = "Past orders:\n"
                for o in orders:
                    msg += f"- {o['date']}: {o['items']} (₹{o['total']}) [{o['status']}]\n"
                return msg
            return result["message"]

        elif function_name == "check_weather_and_suggest":
            from app.tools.vertical.restaurant_tools import WeatherOrderTool
            tool = WeatherOrderTool()
            city = function_args.get("city", "Pune")
            result = await tool.run(method="check_weather_and_suggest", city=city)
            return result["message"]

        # ── Tiffin ─────────────────────────────────────────────────
        elif function_name == "get_todays_menu":
            from app.tools.vertical.tiffin_tools import MenuPlannerTool
            tool = MenuPlannerTool()
            result = await tool.run(method="get_todays_menu", spreadsheet_id=sheet_id)
            return result["data"].get("formatted_message", result["message"]) if result["success"] else result["message"]

        elif function_name == "create_subscription":
            from app.tools.vertical.tiffin_tools import SubscriptionTool
            tool = SubscriptionTool()
            result = await tool.run(
                method="create_subscription",
                spreadsheet_id=sheet_id,
                customer_phone=customer_phone,
                customer_name=customer_name,
                plan_type=function_args.get("plan_type", "both"),
                delivery_address=function_args.get("delivery_address", ""),
            )
            return result["message"]

        elif function_name == "pause_subscription":
            from app.tools.vertical.tiffin_tools import SubscriptionTool
            tool = SubscriptionTool()
            result = await tool.run(
                method="pause_subscription",
                spreadsheet_id=sheet_id,
                customer_phone=customer_phone,
                from_date=function_args.get("from_date", ""),
                to_date=function_args.get("to_date", ""),
            )
            return result["message"]

        elif function_name == "resume_subscription":
            from app.tools.vertical.tiffin_tools import SubscriptionTool
            tool = SubscriptionTool()
            result = await tool.run(method="resume_subscription", spreadsheet_id=sheet_id, customer_phone=customer_phone)
            return result["message"]

        # ── Salon ──────────────────────────────────────────────────
        elif function_name == "get_salon_slots":
            from app.tools.vertical.salon_tools import StaffCalendarTool
            tool = StaffCalendarTool()
            result = await tool.run(
                method="get_next_available_slot",
                spreadsheet_id=sheet_id,
                service_type=function_args.get("service_type", ""),
                preferred_date=function_args.get("preferred_date"),
                preferred_staff=function_args.get("preferred_staff"),
            )
            return result["message"]

        elif function_name == "book_salon_appointment":
            from app.tools.vertical.salon_tools import StaffCalendarTool
            tool = StaffCalendarTool()
            result = await tool.run(
                method="book_appointment",
                spreadsheet_id=sheet_id,
                customer_phone=customer_phone,
                customer_name=customer_name,
                service=function_args.get("service", ""),
                staff=function_args.get("staff", "Any"),
                date=function_args.get("date", ""),
                time=function_args.get("time", ""),
            )
            return result["message"]

        elif function_name == "get_loyalty_status":
            from app.tools.vertical.salon_tools import LoyaltyTool
            tool = LoyaltyTool()
            result = await tool.run(method="get_loyalty_status", spreadsheet_id=sheet_id, customer_phone=customer_phone)
            return result["message"]

        # ── Clinic ─────────────────────────────────────────────────
        elif function_name == "generate_token":
            from app.tools.vertical.clinic_tools import QueueTool
            tool = QueueTool()
            result = await tool.run(
                method="generate_token",
                spreadsheet_id=sheet_id,
                patient_name=customer_name,
                patient_phone=customer_phone,
                reason=function_args.get("reason", ""),
            )
            return result["message"]

        elif function_name == "get_queue_status":
            from app.tools.vertical.clinic_tools import QueueTool
            tool = QueueTool()
            result = await tool.run(method="get_queue_status", spreadsheet_id=sheet_id)
            return result["message"]

        # ── Kirana ─────────────────────────────────────────────────
        elif function_name == "search_catalog":
            from app.tools.vertical.kirana_tools import CatalogTool
            tool = CatalogTool()
            result = await tool.run(method="search_catalog", spreadsheet_id=sheet_id, query=function_args.get("query", ""))
            if result["success"] and result["data"].get("results"):
                items = result["data"]["results"]
                msg = f"Found {len(items)} results:\n"
                for it in items:
                    msg += f"- {it['name']} ({it.get('brand','')}) — ₹{it.get('price','?')}, Stock: {it.get('stock','?')}\n"
                return msg
            return result["message"]

        elif function_name == "get_udhar_balance":
            from app.tools.vertical.kirana_tools import UdharTool
            tool = UdharTool()
            result = await tool.run(method="get_balance", spreadsheet_id=sheet_id, customer_phone=customer_phone)
            return result["message"]

        # ── Coaching ───────────────────────────────────────────────
        elif function_name == "get_attendance_report":
            from app.tools.vertical.coaching_tools import AttendanceTool
            tool = AttendanceTool()
            result = await tool.run(
                method="get_attendance_report",
                spreadsheet_id=sheet_id,
                student_phone=customer_phone,
                month=function_args.get("month"),
            )
            return result["message"]

        elif function_name == "get_pending_fees":
            from app.tools.vertical.coaching_tools import FeeManagementTool
            tool = FeeManagementTool()
            result = await tool.run(method="get_pending_fees", spreadsheet_id=sheet_id)
            return result["message"]

        # ── Gym ────────────────────────────────────────────────────
        elif function_name == "check_membership":
            from app.tools.vertical.gym_tools import MembershipTool
            tool = MembershipTool()
            result = await tool.run(method="check_membership_status", spreadsheet_id=sheet_id, customer_phone=customer_phone)
            return result["message"]

        elif function_name == "get_class_schedule":
            from app.tools.vertical.gym_tools import ClassBookingTool
            tool = ClassBookingTool()
            result = await tool.run(method="get_class_schedule", spreadsheet_id=sheet_id)
            return result["message"]

        elif function_name == "book_class":
            from app.tools.vertical.gym_tools import ClassBookingTool
            tool = ClassBookingTool()
            result = await tool.run(
                method="book_class",
                spreadsheet_id=sheet_id,
                customer_phone=customer_phone,
                class_date=function_args.get("class_date", ""),
                class_time=function_args.get("class_time", ""),
            )
            return result["message"]

        # ── Distance (shared) ──────────────────────────────────────
        elif function_name == "check_delivery_distance":
            from app.tools.maps.distance_tool import DistanceTool
            tool = DistanceTool()
            result = await tool.run(
                method="calculate_distance",
                origin=function_args.get("origin", ""),
                destination=function_args.get("destination", ""),
            )
            return result["message"]

        else:
            return f"Unknown vertical tool: {function_name}"

    except Exception as e:
        logger.error(f"Vertical tool execution failed [{function_name}]: {e}")
        return f"Tool error: {str(e)[:200]}"
