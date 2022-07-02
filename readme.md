[![starlette_async_wstc](https://circleci.com/gh/Randomneo/starlette_async_wstc.svg?style=svg)](https://circleci.com/gh/Randomneo/starlette_async_wstc)

[![PyPI version](https://badge.fury.io/py/starlette_async_wstc.svg)](https://badge.fury.io/py/starlette_async_wstc)

[![Coverage Status](https://coveralls.io/repos/github/Randomneo/starlette_async_wstc/badge.svg?branch=master)](https://coveralls.io/github/Randomneo/starlette_async_wstc?branch=master)


# Description

Modification of Starlette TestClient to support async calls.
Provides async `receive*`, `send*` for `WebSocketTestSession`.

This module is meant to be used with `pytest-asyncio`.


# Installation

    pip install starlette_async_wstc


# Usage example

    from starlette_async_wstc import TestClient
    from somwhere import app   # starlette/fastapi app

    async def test():
        client = TestClient(app)
        async with client.websocket_connect('/ws') as wsclient:
            await wsclient.send_json({'data': 'test_data'})
            resp = await wsclient.receive_json()
            assert resp == {}
