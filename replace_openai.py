import os

filepath = r"d:\Catalyst Nexus\catalyst-nexus-plugins\app\api\whatsapp.py"
with open(filepath, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('AsyncAzureOpenAI', 'AsyncOpenAI')

old_client = """def _get_llm_client() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version="2024-02-15-preview",
        )
    return _llm_client"""

new_client = """def _get_llm_client() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
        )
    return _llm_client"""

text = text.replace(old_client, new_client)
text = text.replace('settings.AZURE_DEPLOYMENT_NAME', '"gpt-4o-mini"')

# The user mentioned "bot is not responding to selected config when i say hi it shoud replay with hi this is your sallon bot"
# When the owner says "Hi", it hits _handle_owner_message which expects training data. If intent is not recognized, it might complain or fail.
# Let's fix _handle_owner_message so that if intent is vague or empty (like "hi") it introduces itself properly as the salon/mess/etc bot!

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(text)

print("Done updating whatsapp.py")
