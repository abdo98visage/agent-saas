import asyncio, uvicorn
from asyncio import WindowsSelectorEventLoopPolicy
asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
uvicorn.run('app.main:app', host='127.0.0.1', port=8002)
