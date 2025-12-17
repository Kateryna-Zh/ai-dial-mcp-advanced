from typing import Any

from mcp_server.models.user_info import UserCreate
from mcp_server.tools.users.base import BaseUserServiceTool


class CreateUserTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        #TProvide tool name as `add_user`
        return "add_user"

    @property
    def description(self) -> str:
        #TProvide description of this tool
        return "Adds new user"

    @property
    def input_schema(self) -> dict[str, Any]:
        #TProvide tool params Schema. To do that you can create json schema from UserCreate pydentic model ` UserCreate.model_json_schema()`
        return UserCreate.model_json_schema()

    async def execute(self, arguments: dict[str, Any]) -> str:
        try:
            # 1. Validate arguments with `UserCreate.model_validate`
            new_user = UserCreate.model_validate(arguments)
            # 2. Call user_client add user and return its results (it is async, don't forget to await)
            return await self._user_client.add_user(new_user)
        
        except Exception as e:
            return f"Error while creating a new user: {str(e)}"