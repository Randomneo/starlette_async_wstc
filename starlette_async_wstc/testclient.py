import asyncio
import io
import json
import types
import typing
from urllib.parse import unquote
from urllib.parse import urlsplit

import anyio
import requests
from starlette.testclient import ASGI2App
from starlette.testclient import ASGI3App
from starlette.testclient import TestClient as starlette_TestClient
from starlette.testclient import WebSocketTestSession as starlette_WebSocketTestSession
from starlette.testclient import _ASGIAdapter as starlette_ASGIAdapter
from starlette.testclient import _AsyncBackend
from starlette.testclient import _get_reason_phrase
from starlette.testclient import _is_asgi3
from starlette.testclient import _MockOriginalResponse
from starlette.testclient import _PortalFactoryType
from starlette.testclient import _Upgrade
from starlette.testclient import _WrapASGI2
from starlette.types import Message
from starlette.types import Scope


class AsyncWebSocketTestSession(starlette_WebSocketTestSession):
    def __init__(
        self,
        app: ASGI3App,
        scope: Scope,
        portal_factory: _PortalFactoryType,
    ) -> None:
        self.app = app
        self.scope = scope
        self.accepted_subprotocol = None
        self.extra_headers = None
        self.portal_factory = portal_factory
        self._receive_queue: "asyncio.Queue[typing.Any]" = asyncio.Queue()
        self._send_queue: "asyncio.Queue[typing.Any]" = asyncio.Queue()

    async def __aenter__(self) -> "AsyncWebSocketTestSession":
        self.task = asyncio.create_task(self._run())
        await self.send({"type": "websocket.connect"})
        message = await self.receive()
        self._raise_on_close(message)
        self.accepted_subprotocol = message.get("subprotocol", None)
        self.extra_headers = message.get("headers", None)
        return self

    async def __aexit__(self, *args: typing.Any) -> None:
        await self.close(1000)
        while not self._send_queue.empty():
            message = await self._send_queue.get()
            if isinstance(message, BaseException):
                raise message
        try:
            self.task.cancel()
            await self.task
        except asyncio.CancelledError:
            pass

    async def _run(self) -> None:
        """
        The sub-thread in which the websocket session runs.
        """
        scope = self.scope
        receive = self._asgi_receive
        send = self._asgi_send
        try:
            while True:
                await self.app(scope, receive, send)
        except BaseException as exc:
            await self._send_queue.put(exc)
            raise

    async def _asgi_receive(self) -> Message:
        return await self._receive_queue.get()

    async def _asgi_send(self, message: Message) -> None:
        await self._send_queue.put(message)

    async def send(self, message: Message) -> None:
        await self._receive_queue.put(message)

    async def send_text(self, data: str) -> None:
        await self.send({"type": "websocket.receive", "text": data})

    async def send_bytes(self, data: bytes) -> None:
        await self.send({"type": "websocket.receive", "bytes": data})

    async def send_json(self, data: typing.Any, mode: str = "text") -> None:
        assert mode in ["text", "binary"]
        text = json.dumps(data)
        if mode == "text":
            await self.send({"type": "websocket.receive", "text": text})
        else:
            await self.send({"type": "websocket.receive", "bytes": text.encode("utf-8")})

    async def receive(self) -> Message:
        message = await self._send_queue.get()
        if isinstance(message, BaseException):
            raise message
        return message

    async def receive_text(self) -> str:
        message = await self.receive()
        self._raise_on_close(message)
        return message["text"]

    async def receive_bytes(self) -> bytes:
        message = await self.receive()
        self._raise_on_close(message)
        return message["bytes"]

    async def receive_json(self, mode: str = "text") -> typing.Any:
        assert mode in ["text", "binary"]
        message = await self.receive()
        self._raise_on_close(message)
        if mode == "text":
            text = message["text"]
        else:
            text = message["bytes"].decode("utf-8")
        return json.loads(text)

    async def close(self, code: int = 1000) -> None:
        await self.send({"type": "websocket.disconnect", "code": code})


class _ASGIAdapter(starlette_ASGIAdapter):   # pragma: no cover
    websocket_session_factory = AsyncWebSocketTestSession

    def __init__(self, *args, **kwargs):
        self.websocket_session_factory = kwargs.pop('websocket_session_factory', self.websocket_session_factory)
        super().__init__(*args, **kwargs)

    def send(
            self,
            request: requests.PreparedRequest,
            *args: typing.Any,
            **kwargs: typing.Any,
    ) -> requests.Response:
        scheme, netloc, path, query, fragment = (
            str(item) for item in urlsplit(request.url)
        )

        default_port = {"http": 80, "ws": 80, "https": 443, "wss": 443}[scheme]

        if ":" in netloc:
            host, port_string = netloc.split(":", 1)
            port = int(port_string)
        else:
            host = netloc
            port = default_port

        # Include the 'host' header.
        if "host" in request.headers:
            headers: typing.List[typing.Tuple[bytes, bytes]] = []
        elif port == default_port:
            headers = [(b"host", host.encode())]
        else:
            headers = [(b"host", (f"{host}:{port}").encode())]

        # Include other request headers.
        headers += [
            (key.lower().encode(), value.encode())
            for key, value in request.headers.items()
        ]

        scope: typing.Dict[str, typing.Any]

        if scheme in {"ws", "wss"}:
            subprotocol = request.headers.get("sec-websocket-protocol", None)
            if subprotocol is None:
                subprotocols: typing.Sequence[str] = []
            else:
                subprotocols = [value.strip() for value in subprotocol.split(",")]
            scope = {
                "type": "websocket",
                "path": unquote(path),
                "raw_path": path.encode(),
                "root_path": self.root_path,
                "scheme": scheme,
                "query_string": query.encode(),
                "headers": headers,
                "client": ["testclient", 50000],
                "server": [host, port],
                "subprotocols": subprotocols,
            }
            session = self.websocket_session_factory(self.app, scope, self.portal_factory)
            raise _Upgrade(session)

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(path),
            "raw_path": path.encode(),
            "root_path": self.root_path,
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": ["testclient", 50000],
            "server": [host, port],
            "extensions": {"http.response.template": {}},
        }

        request_complete = False
        response_started = False
        response_complete: anyio.Event
        raw_kwargs: typing.Dict[str, typing.Any] = {"body": io.BytesIO()}
        template = None
        context = None

        async def receive() -> Message:
            nonlocal request_complete

            if request_complete:
                if not response_complete.is_set():
                    await response_complete.wait()
                return {"type": "http.disconnect"}

            body = request.body
            if isinstance(body, str):
                body_bytes: bytes = body.encode("utf-8")
            elif body is None:
                body_bytes = b""
            elif isinstance(body, types.GeneratorType):
                try:
                    chunk = body.send(None)
                    if isinstance(chunk, str):
                        chunk = chunk.encode("utf-8")
                    return {"type": "http.request", "body": chunk, "more_body": True}
                except StopIteration:
                    request_complete = True
                    return {"type": "http.request", "body": b""}
            else:
                body_bytes = body

            request_complete = True
            return {"type": "http.request", "body": body_bytes}

        async def send(message: Message) -> None:
            nonlocal raw_kwargs, response_started, template, context

            if message["type"] == "http.response.start":
                assert (
                    not response_started
                ), 'Received multiple "http.response.start" messages.'
                raw_kwargs["version"] = 11
                raw_kwargs["status"] = message["status"]
                raw_kwargs["reason"] = _get_reason_phrase(message["status"])
                raw_kwargs["headers"] = [
                    (key.decode(), value.decode())
                    for key, value in message.get("headers", [])
                ]
                raw_kwargs["preload_content"] = False
                raw_kwargs["original_response"] = _MockOriginalResponse(
                    raw_kwargs["headers"]
                )
                response_started = True
            elif message["type"] == "http.response.body":
                assert (
                    response_started
                ), 'Received "http.response.body" without "http.response.start".'
                assert (
                    not response_complete.is_set()
                ), 'Received "http.response.body" after response completed.'
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if request.method != "HEAD":
                    raw_kwargs["body"].write(body)
                if not more_body:
                    raw_kwargs["body"].seek(0)
                    response_complete.set()
            elif message["type"] == "http.response.template":
                template = message["template"]
                context = message["context"]

        try:
            with self.portal_factory() as portal:
                response_complete = portal.call(anyio.Event)
                portal.call(self.app, scope, receive, send)
        except BaseException as exc:
            if self.raise_server_exceptions:
                raise exc

        if self.raise_server_exceptions:
            assert response_started, "TestClient did not receive any response."
        elif not response_started:
            raw_kwargs = {
                "version": 11,
                "status": 500,
                "reason": "Internal Server Error",
                "headers": [],
                "preload_content": False,
                "original_response": _MockOriginalResponse([]),
                "body": io.BytesIO(),
            }

        raw = requests.packages.urllib3.HTTPResponse(**raw_kwargs)
        response = self.build_response(request, raw)
        if template is not None:
            response.template = template
            response.context = context
        return response


class TestClient(starlette_TestClient):    # pragma: no cover
    def __init__(
            self,
            app: typing.Union[ASGI2App, ASGI3App],
            base_url: str = "http://testserver",
            raise_server_exceptions: bool = True,
            root_path: str = "",
            backend: str = "asyncio",
            backend_options: typing.Optional[typing.Dict[str, typing.Any]] = None,
            **kwargs,
    ) -> None:
        super(starlette_TestClient, self).__init__()
        asgi_adapter = kwargs.pop('asgi_adapter', _ASGIAdapter)
        self.async_backend = _AsyncBackend(
            backend=backend, backend_options=backend_options or {}
        )
        if _is_asgi3(app):
            app = typing.cast(ASGI3App, app)
            asgi_app = app
        else:
            app = typing.cast(ASGI2App, app)
            asgi_app = _WrapASGI2(app)  #  type: ignore
        adapter = asgi_adapter(
            asgi_app,
            portal_factory=self._portal_factory,
            raise_server_exceptions=raise_server_exceptions,
            root_path=root_path,
        )
        self.mount("http://", adapter)
        self.mount("https://", adapter)
        self.mount("ws://", adapter)
        self.mount("wss://", adapter)
        self.headers.update({"user-agent": "testclient"})
        self.app = asgi_app
        self.base_url = base_url
