import pytest
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocketDisconnect


@pytest.fixture
def default_app():
    async def ws_endpoint(ws):
        await ws.accept()
        while True:
            try:
                data = await ws.receive_json()
            except WebSocketDisconnect:
                break
            await ws.send_json({'type': 'pingback', 'data': data})
        ws.close()

    return Starlette(routes=[
        WebSocketRoute('/ws', ws_endpoint),
    ])


@pytest.fixture
def text_app():
    async def ws_endpoint(ws):
        await ws.accept()
        while True:
            try:
                data = await ws.receive_text()
            except WebSocketDisconnect:
                break
            await ws.send_text(data)
        ws.close()

    return Starlette(routes=[
        WebSocketRoute('/ws', ws_endpoint),
    ])


@pytest.fixture
def bytes_app():
    async def ws_endpoint(ws):
        await ws.accept()
        while True:
            try:
                data = await ws.receive_bytes()
            except WebSocketDisconnect:
                break
            await ws.send_bytes(data)
        ws.close()

    return Starlette(routes=[
        WebSocketRoute('/ws', ws_endpoint),
    ])
