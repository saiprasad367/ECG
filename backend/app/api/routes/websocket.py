import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.database.redis_client import get_redis

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)

# In-memory registry: session_id -> set of WebSocket connections
_connections: dict[str, set[WebSocket]] = {}


def _register(session_id: str, ws: WebSocket):
    if session_id not in _connections:
        _connections[session_id] = set()
    _connections[session_id].add(ws)


def _unregister(session_id: str, ws: WebSocket):
    if session_id in _connections:
        _connections[session_id].discard(ws)


async def broadcast_to_session(session_id: str, payload: dict):
    """Send payload to all WebSocket clients for a session."""
    sockets = list(_connections.get(session_id, []))
    dead = []
    for ws in sockets:
        try:
            await ws.send_text(json.dumps(payload, default=str))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _unregister(session_id, ws)


@router.websocket("/ws/session/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    _register(session_id, websocket)
    logger.info(f"WebSocket connected for session {session_id}")

    # Send initial connected message
    await websocket.send_text(json.dumps({
        "type": "connected",
        "session_id": session_id,
        "message": "Real-time updates active",
    }))

    redis = get_redis()
    pubsub = None

    try:
        if redis:
            # Subscribe to Redis pub/sub channel for this session
            pubsub = redis.pubsub()
            await pubsub.subscribe(f"ws:{session_id}")

            async def redis_listener():
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            await broadcast_to_session(session_id, data)
                        except Exception as e:
                            logger.debug(f"Redis pubsub parse error: {e}")

            listener_task = asyncio.create_task(redis_listener())

            # Keep alive loop — wait for client disconnect
            try:
                while True:
                    try:
                        msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                        # Echo ping/pong
                        if msg == "ping":
                            await websocket.send_text(json.dumps({"type": "pong"}))
                    except asyncio.TimeoutError:
                        # Send heartbeat
                        await websocket.send_text(json.dumps({"type": "heartbeat"}))
            except (WebSocketDisconnect, Exception):
                pass
            finally:
                listener_task.cancel()
                await pubsub.unsubscribe(f"ws:{session_id}")
        else:
            # No Redis: just keep connection open with heartbeats
            while True:
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                    if msg == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                except asyncio.TimeoutError:
                    await websocket.send_text(json.dumps({"type": "heartbeat"}))
                except WebSocketDisconnect:
                    break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        _unregister(session_id, websocket)
        logger.info(f"WebSocket cleaned up for session {session_id}")
