from typing import Any

from mcp_server.models.user_info import UserUpdate
from mcp_server.tools.users.base import BaseUserServiceTool


class UpdateUserTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        #Provide tool name as `update_user`
        return "update_user"

    @property
    def description(self) -> str:
        #Provide description of this tool
        return 'Updates user'

    @property
    def input_schema(self) -> dict[str, Any]:
        # Provide tool params Schema:
        # - id: number, required, User ID that should be updated.
        # - new_info: UserUpdate.model_json_schema()
        return {
            "type": "object",
            "properties": {
                "id": {
                    "type": "number",
                    "description": "User ID that should be updated."
                },
                "new_info": UserUpdate.model_json_schema()
            },
            "required": ["id"]
        }


    async def execute(self, arguments: dict[str, Any]) -> str:
        #TODO:
        # 1. Get user `id` from `arguments`
        # 2. Get `new_info` from `arguments` and create `UserUpdate` via pydentic `UserUpdate.model_validate`
        # 3. Call user_client update_user and return its results (it is async, don't forget to await)
        try:
            user_id = arguments["id"]
            user = UserUpdate.model_validate(arguments["new_info"])
            return await self._user_client.update_user(user_id=user_id, user_update_model=user)
        # 4. Optional: You can wrap it with `try-except` and return error as string `f"Error while creating a new user: {str(e)}"`
        except Exception as e:
            return f"Error while creating a new user: {str(e)}"

