import asyncio, sys
sys.path.insert(0, "/app")
from app.handlers.commands import handle_auth

async def t():
    try:
        r = await handle_auth("web", "test123", "test_login", "1234567890")
        print("SUCCESS:", r)
    except Exception as e:
        import traceback
        print("ERROR:", type(e).__name__, str(e))
        traceback.print_exc()

asyncio.run(t())
