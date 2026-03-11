import asyncio
import os
from typing import Dict, Any, List

from app.tools.base_tool import BaseTool
from app.core.config import settings

class RouteTool(BaseTool):
    """
    Maps Tool: Route Optimization
    Optimizes a multi-stop delivery path (Traveling Salesperson Problem).
    Invaluable for Tiffin services, flower deliveries, or Gym supplement drops to 
    plan the fastest physical sequence for a delivery boy.
    """

    @property
    def tool_name(self) -> str:
        return "RouteTool"

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Dispatcher for Route Planning actions."""
        method_name = kwargs.pop("method", None)
        
        if not method_name:
            return self._format_response(success=False, message="Missing 'method' parameter.")
            
        try:
            if method_name == "optimize_delivery_route":
                return await self.optimize_delivery_route(**kwargs)
            elif method_name == "generate_delivery_route_message":
                return await self.generate_delivery_route_message(**kwargs)
            else:
                return self._format_response(success=False, message=f"Unknown method '{method_name}'")
        except Exception as e:
            return self.handle_error(e)

    async def mock_execute(self, **kwargs) -> Dict[str, Any]:
        """Skip hitting the expensive API and just return mock directions."""
        method_name = kwargs.get("method")
        
        if method_name == "optimize_delivery_route":
            # Mock return
            destinations = kwargs.get("destinations", [])
            optim = [{"address": v, "original_index": i} for i, v in enumerate(destinations)]
            
            return self._format_response(
                success=True,
                data={
                    "optimized_destinations": optim,
                    "total_distance_km": 15.5,
                    "estimated_time_mins": 45
                },
                message=f"Mock: Generated optimized route for {len(destinations)} stops."
            )
        return await super().mock_execute(**kwargs)

    async def optimize_delivery_route(self, origin: str, destinations: List[str]) -> Dict[str, Any]:
        """
        Takes a highly inefficient list of delivery addresses and asks Google to 
        sort them logically into the fastest drivable path.
        """
        if not settings.GOOGLE_MAPS_API_KEY:
            return self._format_response(success=False, message="GOOGLE_MAPS_API_KEY not configured.")
        
        if not destinations:
            return self._format_response(success=False, message="No destinations provided.")
            
        try:
            import googlemaps
            gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
            
            if len(destinations) == 1:
                # No optimization needed
                return self._format_response(
                    success=True,
                    data={"optimized_destinations": [{"address": destinations[0], "original_index": 0}]}
                )
                
            # Pop the final destination to act as the official 'destination' in Google Maps logic
            final_dest = destinations[-1]
            waypoints = destinations[:-1]
            
            # Request route, setting optimize_waypoints=True solves the Traveling Salesperson
            directions_result = await asyncio.to_thread(
                gmaps.directions,
                origin=origin,
                destination=final_dest,
                waypoints=waypoints,
                optimize_waypoints=True,
                mode="driving"
            )
            
            if directions_result:
                route = directions_result[0]
                waypoint_order = route.get("waypoint_order", [])
                
                # Reconstruct the optimized list based on Google's sorting
                optimized_list = []
                for idx in waypoint_order:
                    optimized_list.append({
                        "address": waypoints[idx],
                        "original_index": idx
                    })
                
                # Append the final actual destination
                optimized_list.append({
                    "address": final_dest,
                    "original_index": len(destinations) - 1
                })
                
                return self._format_response(
                    success=True,
                    data={"optimized_destinations": optimized_list},
                    message=f"Successfully optimized sequence for {len(destinations)} stops."
                )

            return self._format_response(success=False, message="Google Maps returned no routes.")

        except ImportError:
            return self._format_response(success=False, message="googlemaps package not installed (pip install googlemaps)")
        except Exception as e:
            return self.handle_error(e)

    async def generate_delivery_route_message(self, optimized_destinations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Turns the JSON response into a beautiful, numbered WhatsApp message for the delivery boy."""
        msg = "📍 *Optimized Delivery Route:*\n\n"
        
        for i, dest in enumerate(optimized_destinations, 1):
            msg += f"{i}. {dest['address']}\n"
            
        msg += "\nDrive safely! 🛵"
        
        return self._format_response(
            success=True,
            data={"whatsapp_message": msg},
            message="Message formatting complete."
        )
