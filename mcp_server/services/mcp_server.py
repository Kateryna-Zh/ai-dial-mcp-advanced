import uuid
import asyncio

from mcp_server.models.request import MCPRequest
from mcp_server.models.response import MCPResponse, ErrorResponse
from mcp_server.tools.users.create_user_tool import CreateUserTool
from mcp_server.tools.users.delete_user_tool import DeleteUserTool
from mcp_server.tools.users.get_user_by_id_tool import GetUserByIdTool
from mcp_server.tools.users.search_users_tool import SearchUsersTool
from mcp_server.tools.users.update_user_tool import UpdateUserTool
from mcp_server.tools.users.user_client import UserClient


class MCPSession:
    """Represents an MCP session with state management"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.ready_for_operation = False
        self.created_at = asyncio.get_event_loop().time()
        self.last_activity = self.created_at


class MCPServer:

    def __init__(self):
        self.protocol_version = "2024-11-05"
        self.server_info = {
            "name": "custom-ums-mcp-server",
            "version": "1.0.0"
        }

        # Session management
        self.sessions: dict[str, MCPSession] = {}
        self.tools = {}
        self._register_tools()

    def _register_tools(self):
        """Register all available tools"""

        # 1. Crate UserClient
        user_client = UserClient()
        # 2. Create list of tools: GetUserByIdTool, SearchUsersTool, CreateUserTool, UpdateUserTool, DeleteUserTool
        tools_list = [
            GetUserByIdTool(user_client), 
            SearchUsersTool(user_client), 
            CreateUserTool(user_client), 
            UpdateUserTool(user_client), 
            DeleteUserTool(user_client)
        ]
        # 3. Iterate trough list and add them to `self.tools` dict where key is tool name and value is tool itself
        for tool in tools_list:
            self.tools[tool.name] = tool

    def _validate_protocol_version(self, client_version: str) -> str:
        """Validate and negotiate protocol version"""
        supported_versions = ["2024-11-05"]
        if client_version in supported_versions:
            return client_version
        return self.protocol_version

    def get_session(self, session_id: str) -> MCPSession | None:
        """Get an existing session"""
        session = self.sessions.get(session_id)
        if session:
            session.last_activity = asyncio.get_event_loop().time()
        return session

    def handle_initialize(self, request: MCPRequest) -> tuple[MCPResponse, str]:
        """Handle initialization request with session creation"""
        # 1. Create and assign to new `session_id` session ID as `str(uuid.uuid4()).replace("-", "")`
        session_id = str(uuid.uuid4()).replace("-", "")
        # 2. Create MCPSession with `session_id` and assign to `session`
        session = MCPSession(session_id)
        self.sessions[session_id] = session
        # 3. Handle protocol version and assign to `protocol_version` variable:
        protocol_version = request.params.get("protocolVersion") if request.params else self.protocol_version
        # 4. Create MCPResponse:
        #       - id=request.id
        #       - result={
        #                 "protocolVersion": protocol_version,
        #                 "capabilities": {
        #                     "tools": {},
        #                     "resources": {},
        #                     "prompts": {}
        #                 },
        #                 "serverInfo": self.server_info
        #             }
        response = MCPResponse(
            id=request.id,
            result={
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "serverInfo": self.server_info
            }
        )
        # 5. Return created MCP response and `session_id`
        return response, session_id

    def handle_tools_list(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/list request"""
        # 1. Create `tools_list` by iterating through `self.tools.values()` and calling `to_mcp_tool()` on each tool (via comprehension)
        tools_list = [tool.to_mcp_tool() for tool in self.tools.values()]
        # 2. Create MCPResponse:
        #       - id=request.id
        #       - result={"tools": tools_list}
        response = MCPResponse(
            id = request.id,
            result={"tools": tools_list}
        )
        # 3. Return created MCP response
        return response

    async def handle_tools_call(self, request: MCPRequest) -> MCPResponse:
        """Handle tools/call request with proper MCP-compliant response format"""

        # 1. Check if `request.params` exists, if not return MCPResponse with error:
        #       - id=request.id
        #       - error=ErrorResponse(code=-32602, message="Missing parameters")
        if not request.params:
            return MCPResponse(
                id=request.id,
                error=ErrorResponse(code=32602, message="Missing parameters")
            )
        # 2. Extract `tool_name` from `request.params.get("name")` and `arguments` from `request.params.get("arguments", {})`
        tool_name = request.params.get("name")
        arguments = request.params.get("arguments", {})
        # 3. Check if `tool_name` exists, if not return MCPResponse with error:
        #       - id=request.id
        #       - error=ErrorResponse(code=-32602, message="Missing required parameter: name")
        if not tool_name:
            return MCPResponse(
                id=request.id,
                error=ErrorResponse(code=32602, message="Missing required parameter: name")
            )
        # 4. Check if `tool_name` exists in `self.tools`, if not return MCPResponse with error:
        #       - id=request.id
        #       - error=ErrorResponse(code=-32601, message=f"Tool '{tool_name}' not found")
        if not tool_name in self.tools:
            return MCPResponse(
                id=request.id,
                error=ErrorResponse(code=32601, message=f"Tool '{tool_name}' not found")
            )
        # 5. Get `tool` from `self.tools[tool_name]`
        tool = self.tools[tool_name]
        # 6. Try to execute tool with arguments:
        #       - Call `await tool.execute(arguments)` and assign result to `result_text`
        #       - Return MCPResponse with id=request.id and result={"content": [{"type": "text", "text": result_text}]}
        # 7. Handle exceptions by returning MCPResponse with:
        #       - id=request.id
        #       - result={"content": [{"type": "text", "text": f"Tool execution error: {str(tool_error)}"}], "isError": True}
        try:
            result = await tool.execute(arguments)
            return MCPResponse(
                id=request.id,
                result={
                    "content": [{"type": "text",
                                 "text": result}]
                }
            )
        except Exception as e:
            return MCPResponse(
                id=request.id,
                result={
                    "content": [{"type": "text",
                                 "text": f"Tool execution error: {str(e)}"}],
                    "isError": True
                }
            )