import asyncio
from typing import List, Dict
from fastapi import Request
from fastapi.responses import StreamingResponse


class SSEManager:
    """Server-Sent Events manager for real-time admin updates."""

    def __init__(self):
        self._clients: List[asyncio.Queue] = []

    async def subscribe(self, request: Request):
        queue: asyncio.Queue = asyncio.Queue()
        self._clients.append(queue)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event
                except asyncio.TimeoutError:
                    # Send a keep-alive comment to prevent connection timeout
                    yield ":keepalive\n\n"
        finally:
            if queue in self._clients:
                self._clients.remove(queue)

    def broadcast(self, data: Dict):
        event = f"data: {__import__('json').dumps(data)}\n\n"
        # Remove disconnected clients lazily
        active = []
        for queue in self._clients:
            try:
                queue.put_nowait(event)
                active.append(queue)
            except asyncio.QueueFull:
                pass
        self._clients = active

    def notify_new_message(self, from_number: str, text_preview: str):
        self.broadcast({
            "type": "new_message",
            "from_number": from_number,
            "text_preview": text_preview,
        })

    def notify_status_change(self, provider_message_id: str, status: str):
        self.broadcast({
            "type": "status_change",
            "message_id": provider_message_id,
            "status": status,
        })


sse_manager = SSEManager()