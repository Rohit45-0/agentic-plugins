import asyncio
from openai import AsyncOpenAI
import os

client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

async def test():
    ex_add = "'add paneer tikka 250 rs to menu' → ADD|Paneer Tikka - ₹250"
    ex_rm = "'remove dosa from menu' → REMOVE|Dosa"
    ex_query = "'what items do we have?' → QUERY|what items do we have"
    ex_save = "'we are open 9am to 10pm' → SAVE|Business hours: 9 AM to 10 PM"
    ex_cancel = "'cancel booking for 9876543210 on 2026-03-02' → CANCEL|<phone_number>|<YYYY-MM-DD>"
    ex_cancel_all = "'cancel all bookings for today' → CANCEL|ALL|<YYYY-MM-DD>"

    msg = "I mean cancel all appointments for today"

    intent_resp = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": (
                "You classify business owner messages into intents. "
                "Reply with ONLY one of these formats:\n"
                f"ADD|<clean item/info to add> - when owner wants to add something (e.g. {ex_add})\n"
                f"REMOVE|<item to remove> - when owner wants to remove/delete something (e.g. {ex_rm})\n"
                f"QUERY|<question> - when owner is asking a question (e.g. {ex_query})\n"
                f"SAVE|<info> - when owner shares business info/facts to remember (e.g. {ex_save})\n"
                f"GREET|hello - when owner just says hi, hello, or tests the bot.\n"
                f"CANCEL|<phone_number>|<date> - when owner wants to completely cancel a specific customer's booking. (e.g. {ex_cancel})\n"
                f"CANCEL|ALL|<date> - when owner wants to cancel ALL schedule/appointments for a day. (e.g. {ex_cancel_all})\n"
                "Always clean up and format the content nicely. Support Hindi/Marathi/Hinglish."
            )
        }, {
            "role": "user",
            "content": msg
        }],
        max_tokens=200,
        temperature=0.1,
    )
    print("OUTPUT WITHOUT DATE:", intent_resp.choices[0].message.content)

asyncio.run(test())
