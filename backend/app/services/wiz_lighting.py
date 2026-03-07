"""
WiZ bulb lighting service using local UDP control via pywizlight.
"""
import asyncio
from pywizlight import wizlight, PilotBuilder


BULB_IP = "192.168.1.48"


class WizLightingService:
    async def apply_recommendation(self, color_temp_kelvin: int, brightness_percent: int) -> None:
        """
        Apply a lighting recommendation to the WiZ bulb.

        Args:
            color_temp_kelvin: Color temperature in Kelvin (e.g. 2700–6500)
            brightness_percent: Brightness from 0–100%
        """
        brightness = round(brightness_percent / 100 * 255)
        brightness = max(0, min(255, brightness))

        bulb = wizlight(BULB_IP)
        try:
            await bulb.turn_on(
                PilotBuilder(colortemp=color_temp_kelvin, brightness=brightness)
            )
        finally:
            await bulb.async_close()
