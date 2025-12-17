from typing import Any

from mcp_server.tools.users.base import BaseUserServiceTool


class SearchUsersTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        #Provide tool name as `search_users`
        return "search_users"

    @property
    def description(self) -> str:
        #Provide description of this tool
        return "Search users by name, surname, email, gender (all params are optional)"

    @property
    def input_schema(self) -> dict[str, Any]:
        # Provide tool params Schema:
        # - name: str
        # - surname: str
        # - email: str
        # - gender: str
        # None of them are required (see UserClient.search_users method)
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "User name"
                },
                "surname": {
                    "type": "string",
                    "description": "User surname"
                },
                "email": {
                    "type": "string",
                    "description": "User email"
                },
                "gender": {
                    "type": "string",
                    "description": "User gender",
                    "enum": [
                        "male",
                        "female"
                    ],
                },
            },
            "required": []
        }


    async def execute(self, arguments: dict[str, Any]) -> str:
        # Call user_client search_users (with `**arguments`) and return its results (it is async, don't forget to await)
        try:
            return await self._user_client.search_users(**arguments)
        except Exception as e:
            return f"Error while searching users: {str(e)}"