import asyncio
import os
from typing import Dict, Any

from app.tools.base_tool import BaseTool
from app.core.config import settings

class DistanceTool(BaseTool):
    """
    Maps Tool: Distance & Radius
    Calculates exact driving distance and time between two physical addresses or GPS coordinates.
    Crucial for Tiffin and Restaurant bots to dynamically reject out-of-bounds orders or calculate delivery fees.
    """

    @property
    def tool_name(self) -> str:
        return "DistanceTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Dispatcher for Maps Distance actions."""
        method_name = kwargs.pop("method", None)
        
        if not method_name:
            return self._format_response(success=False, message="Missing 'method' parameter.")
            
        try:
            if method_name == "is_within_delivery_radius":
                return await self.is_within_delivery_radius(**kwargs)
            elif method_name == "calculate_delivery_charge":
                return await self.calculate_delivery_charge(**kwargs)
            elif method_name == "get_location_pin_message":
                return await self.get_location_pin_message(**kwargs)
            else:
                return self._format_response(success=False, message=f"Unknown method '{method_name}'")
        except Exception as e:
            return self.handle_error(e)

    async def mock_execute(self, **kwargs) -> Dict[str, Any]:
        """If MOCK_MODE=True, simulate distance without consuming Google APIs."""
        method_name = kwargs.get("method")
        
        if method_name == "is_within_delivery_radius":
            # Simulate a response of 4.2 km
            return self._format_response(
                success=True,
                data={
                    "within_radius": True,
                    "distance_km": 4.2,
                    "estimated_minutes": 15
                },
                message="Mock: Address is within 5km radius."
            )
        elif method_name == "calculate_delivery_charge":
            # 4.2 km * 10 rs/km
            return self._format_response(
                success=True,
                data={"delivery_charge_inr": 42},
                message="Mock: Delivery charge calculated."
            )
            
        return await super().mock_execute(**kwargs)


    async def is_within_delivery_radius(self, business_address: str, customer_address: str, 
                                        max_radius_km: float) -> Dict[str, Any]:
        """
        Uses Google Maps API to calculate accurate driving distance between the shop and the customer.
        Returns whether it's allowed, plus exact distance and time.
        """
        if not settings.GOOGLE_MAPS_API_KEY:
            return self._format_response(success=False, message="GOOGLE_MAPS_API_KEY not configured.")
            
        try:
            import googlemaps
            gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
            
            # Blocking API call, wrapped in to_thread so it doesn't block FastAPI
            directions = await asyncio.to_thread(
                gmaps.distance_matrix,
                origins=[business_address],
                destinations=[customer_address],
                mode="driving"
            )
            
            if directions['status'] == 'OK':
                element = directions['rows'][0]['elements'][0]
                if element['status'] == 'OK':
                    # Extract meters and seconds
                    distance_meters = element['distance']['value']
                    duration_seconds = element['duration']['value']
                    
                    distance_km = distance_meters / 1000.0
                    duration_minutes = round(duration_seconds / 60)
                    
                    is_within = distance_km <= float(max_radius_km)
                    
                    return self._format_response(
                        success=True,
                        data={
                            "within_radius": is_within,
                            "distance_km": distance_km,
                            "estimated_minutes": duration_minutes,
                            "text_distance": element['distance']['text']
                        },
                        message=f"Distance calculated. Within {max_radius_km}km: {is_within}"
                    )
            
            return self._format_response(success=False, message="Could not find a valid driving route on Google Maps.")

        except ImportError:
            return self._format_response(success=False, message="googlemaps package not installed (pip install googlemaps)")
        except Exception as e:
            return self.handle_error(e)

    async def calculate_delivery_charge(self, distance_km: float, base_charge: float, 
                                        per_km_charge: float) -> Dict[str, Any]:
        """Simple mathematical formulation so the AI bots aren't manually calculating math."""
        total_charge = base_charge + (distance_km * per_km_charge)
        return self._format_response(
            success=True,
            data={"delivery_charge_inr": round(total_charge, 2)},
            message=f"Calculated delivery charge: ₹{round(total_charge, 2)}"
        )
        
    async def get_location_pin_message(self, address: str) -> Dict[str, Any]:
        """Generates a perfect, clickable Google Maps URL for the business to send users."""
        import urllib.parse
        encoded_address = urllib.parse.quote_plus(address)
        maps_link = f"https://maps.google.com/?q={encoded_address}"
        return self._format_response(
            success=True,
            data={"maps_url": maps_link},
            message="Location pin generated successfully."
        )
