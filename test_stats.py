import asyncio, json, sys
sys.path.insert(0, "/app")
from app.handlers.commands import handle_my_stats

result = asyncio.run(handle_my_stats(286601))
print(json.dumps(result, indent=2, ensure_ascii=False))
