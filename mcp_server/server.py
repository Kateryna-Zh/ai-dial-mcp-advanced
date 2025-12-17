import json
from inspect import isawaitable
from typing import Optional
from fastapi import FastAPI, Response, Header
from fastapi.responses import StreamingResponse
import uvicorn

from .services.mcp_server import MCPServer
from .models.request import MCPRequest
from .models.response import MCPResponse, ErrorResponse

MCP_SESSION_ID_HEADER = "Mcp-Session-Id"

# FastAPI app
app = FastAPI(title="MCP Tools Server", version="1.0.0")
mcp_server = MCPServer()


def _validate_accept_header(accept_header: Optional[str]) -> bool:
    """Validate that client accepts both JSON and SSE"""
    # 1. Check if `accept_header` is None or falsy, return False if so
    if not accept_header:
        return False
    # 2. Split `accept_header` by commas and create `accept_types` list with stripped and lowercased values
    accept_types = [t.strip().lower() for t in accept_header.split(",")]
    # 3. Check if any type in `accept_types` contains 'application/json' and assign to `has_json`
    has_json = any('application/json' in t for t in accept_types)
    # 4. Check if any type in `accept_types` contains 'text/event-stream' and assign to `has_sse`
    has_sse = any('text/event-stream' in t for t in accept_types)
    # 5. Return `has_json and has_sse`
    return has_json and has_sse

async def _create_sse_stream(messages: list):
    """Create Server-Sent Events stream for responses"""
    dumps = json.dumps
    prefix = "data: "
    suffix = "\n\n"
    for message in messages:
        if isawaitable(message):
            message = await message
        if hasattr(message, "model_dump_json"):
            payload = message.model_dump_json(exclude_none=True)
        elif hasattr(message, "dict"):
            payload = dumps(message.dict(exclude_none=True))
        else:
            payload = dumps(message)
        yield (prefix + payload + suffix).encode("utf-8")
    yield b"data: [DONE]\n\n"

@app.post("/mcp")
async def handle_mcp_request(
        request: MCPRequest,
        response: Response,
        accept: Optional[str] = Header(None),
        mcp_session_id: Optional[str] = Header(None, alias=MCP_SESSION_ID_HEADER)
):
    """Single MCP endpoint handling all JSON-RPC requests with proper session management"""

    # 1. Validate Accept header:
    if not _validate_accept_header(accept):
    #       - If False, create `error_response` with MCPResponse:
    #           - id="server-error",
    #           - error=ErrorResponse(code=-32600, message="Client must accept both application/json and text/event-stream")
        error_response = MCPResponse(
            id="server-error",
            error=ErrorResponse(code=-32600, message="Client must accept both application/json and text/event-stream")
        )
    #       - Return Response with:
    #           - status_code=406,
    #           - content=error_response.model_dump_json(),
    #           - media_type="application/json"
        return Response(
            status_code=406,
            content=error_response.model_dump_json(),
            media_type="application/json"
        )
    # 2. Handle initialization (no session required):
    #       - If `request.method == "initialize"`:
    #           - Call `mcp_server.handle_initialize(request)` and assign to `mcp_response, session_id`
    #           - If `session_id` exists, set `response.headers[MCP_SESSION_ID_HEADER] = session_id` and `mcp_session_id = session_id`
    if request.method == "initialize":
        mcp_response, session_id = mcp_server.handle_initialize(request)
        if session_id:
            response.headers[MCP_SESSION_ID_HEADER] = session_id
            mcp_session_id = session_id
    # 3. Handle other methods (session required):
    else:
    #       - Else block for non-initialize methods:
    #           - Validate `mcp_session_id` exists, if not create error_response with
    #               MCPResponse(id="server-error", error=ErrorResponse(code=-32600, message="Missing session ID"))
    #               and return Response with:
    #                   - status_code=400
    #                   - content=error_response.model_dump_json()
    #                   - media_type="application/json"
        if not mcp_session_id:
            error_response = MCPResponse(
                id="server-error",
                error=ErrorResponse(code=-32600, message="Missing session ID")
            )
            return Response(
                status_code=400,
                content=error_response.model_dump_json(),
                media_type="application/json"
            )
    #           - Get `session` from `mcp_server.get_session(mcp_session_id)`
        session = mcp_server.get_session(mcp_session_id)
    #           - If no session, return Response with:
    #               - status_code=400
    #               - content="No valid session ID provided"
        if not session:
            return Response(
                status_code=400,
                content="No valid session ID provided"
            )
    #           - Handle notifications/initialized: if `request.method == "notifications/initialized"` then set
    #               - `session.ready_for_operation = True`
    #               - then return Response with status_code=202 and headers={MCP_SESSION_ID_HEADER: session.session_id}
        if request.method == "notifications/initialized":
            session.ready_for_operation = True
            return Response(
                status_code=202,
                headers={MCP_SESSION_ID_HEADER: session.session_id}
            )
    #           - Check if session is ready:
    #               - if not `session.ready_for_operation`, then create error_response and return Response with status_code=400
    #                   and MCPResponse(id="server-error", error=ErrorResponse(code=-32600, message="Missing session ID"))
        if not session.ready_for_operation:
            error_response = MCPResponse(
                id="server-error",
                error=ErrorResponse(code=-32600, message="Missing session ID")
            )
            return Response(
                status_code=400,
                content=error_response.model_dump_json(),
                media_type="application/json"
            )
    #           - Handle tools/list: 
        if request.method == "tools/list":
            mcp_response = mcp_server.handle_tools_list(request)
    #           - Handle tools/call: 
        elif request.method == "tools/call":
            mcp_response = mcp_server.handle_tools_call(request)
    #           - Handle unknown methods: 
        else:
            mcp_response = MCPResponse(
                id=request.id, 
                error=ErrorResponse(code=-32602, message=f"Method '{request.method}' not found")
                )
    # 4. Return StreamingResponse:
    #       - content=_create_sse_stream([mcp_response])
    #       - media_type="text/event-stream"
    #       - headers={"Cache-Control": "no-cache", "Connection": "keep-alive", MCP_SESSION_ID_HEADER: mcp_session_id}
    return StreamingResponse(
        content=_create_sse_stream([mcp_response]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", 
                 "Connection": "keep-alive", 
                 MCP_SESSION_ID_HEADER: mcp_session_id}
    )


if __name__ == "__main__":
    uvicorn.run(
        "mcp_server.server:app",
        host="0.0.0.0",
        port=8006,
        reload=True,
        log_level="debug"
    )
