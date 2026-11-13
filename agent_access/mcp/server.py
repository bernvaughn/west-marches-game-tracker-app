"""The single MCP server, mounted in one Django view at /mcp.

Stateless JSON mode: every request is self-contained, so no session state is shared
between threads. Tool bodies are plain sync functions that run on the request thread.
"""

import functools
import inspect
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from asgiref.sync import async_to_sync, sync_to_async
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings

from agent_access.auth import authenticate_bearer

__all__ = ["AgentContext", "ToolError", "agent_tool", "get_agent_context", "mcp_view", "server"]

server = MCPServer(
    "west-marches",
    instructions=(
        "Tools for one Downtime Market club. You can look up characters and items and propose "
        "changes. Nothing you propose changes a balance until a game master confirms it."
    ),
)


@dataclass(frozen=True)
class AgentContext:
    connection: Any
    user: Any
    club: Any


_current: ContextVar[AgentContext] = ContextVar("agent_context")


def get_agent_context() -> AgentContext:
    return _current.get()


def agent_tool(fn):
    """Register `fn(ctx, **args)` as an MCP tool. Returns `fn` so tests can call it directly.

    `fn` is a sync function. Its first argument is the AgentContext; the client never sees it.
    The tool name is the function name and the description is the docstring.

    Annotate the return type as `dict[str, Any]` (or a pydantic model, or
    `list[dict[str, Any]]`). A bare `-> dict` gives the client no `structuredContent`.
    Raise `ToolError("message")` for an error the agent should read.
    """
    signature = inspect.signature(fn)
    params = list(signature.parameters.values())[1:]

    async def wrapper(**kwargs):
        return await sync_to_async(fn)(get_agent_context(), **kwargs)

    functools.update_wrapper(wrapper, fn)
    del wrapper.__wrapped__  # keep the SDK from reading fn's signature (it has ctx)
    wrapper.__signature__ = signature.replace(parameters=params)
    wrapper.__annotations__ = {k: v for k, v in fn.__annotations__.items() if k != "ctx"}
    server.add_tool(wrapper, name=fn.__name__, description=inspect.getdoc(fn))
    return fn


@agent_tool
def whoami(ctx: AgentContext) -> dict[str, Any]:
    """Say which club, user and connection this agent is acting for."""
    return {
        "club": ctx.club.name,
        "club_slug": ctx.club.slug,
        "user": ctx.user.display_name,
        "connection": ctx.connection.label,
    }


def _new_session_manager():
    # `_lowlevel_server` is private SDK API. This is the one place that touches it.
    # A manager's run() works once per instance, so build a fresh one per request.
    return StreamableHTTPSessionManager(
        app=server._lowlevel_server,
        json_response=True,
        stateless=True,
        security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


async def _run_asgi(scope, body):
    manager = _new_session_manager()
    messages = []
    sent_body = False

    async def receive():
        nonlocal sent_body
        if sent_body:
            return {"type": "http.disconnect"}
        sent_body = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    async with manager.run():
        await manager.handle_request(scope, receive, send)
    return messages


def _unauthorized():
    response = JsonResponse({"error": "invalid_token"}, status=401)
    response["WWW-Authenticate"] = "Bearer"
    return response


@csrf_exempt
def mcp_view(request):
    if request.method != "POST":
        response = HttpResponse(status=405)
        response["Allow"] = "POST"
        return response
    connection = authenticate_bearer(request.headers.get("Authorization"))
    if connection is None:
        return _unauthorized()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": request.scheme,
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [
            (k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in request.headers.items()
        ],
        "server": ("localhost", 80),
        "client": None,
    }
    token = _current.set(
        AgentContext(connection=connection, user=connection.user, club=connection.club)
    )
    try:
        messages = async_to_sync(_run_asgi)(scope, request.body)
    finally:
        _current.reset(token)
    status, headers, body = 500, [], b""
    for message in messages:
        if message["type"] == "http.response.start":
            status, headers = message["status"], message.get("headers", [])
        elif message["type"] == "http.response.body":
            body += message.get("body", b"")
    response = HttpResponse(body, status=status)
    for key, value in headers:
        if key.lower() != b"content-length":
            response[key.decode("latin-1")] = value.decode("latin-1")
    return response


from . import tools_batches, tools_items, tools_lookup  # noqa: E402,F401
