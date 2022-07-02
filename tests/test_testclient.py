from starlette_async_wstc import TestClient


async def test_testclient(default_app):
    client = TestClient(default_app)
    async with client.websocket_connect('/ws') as wsclient:
        await wsclient.send_json({'test': 'test_data'})
        resp = await wsclient.receive_json()
        assert resp == {
            'type': 'pingback',
            'data': {
                'test': 'test_data',
            },
        }


async def test_text_client(text_app):
    client = TestClient(text_app)
    async with client.websocket_connect('/ws') as wsclient:
        await wsclient.send_text('test_text')
        resp = await wsclient.receive_text()
        assert resp == 'test_text'


async def test_bytes_client(bytes_app):
    client = TestClient(bytes_app)
    async with client.websocket_connect('/ws') as wsclient:
        await wsclient.send_bytes(b'test_bytes')
        resp = await wsclient.receive_bytes()
        assert resp == b'test_bytes'
