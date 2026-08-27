"""Microsoft Entra ID authorization code flow for the teaching harness."""

from __future__ import annotations

from typing import Any

import msal

SCOPES = ["User.Read"]


class EntraAuth:
    def __init__(self, client_id: str, tenant_id: str, redirect_uri: str) -> None:
        self.redirect_uri = redirect_uri
        self.client = msal.PublicClientApplication(
            client_id=client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )

    def begin_sign_in(self) -> dict[str, Any]:
        return self.client.initiate_auth_code_flow(
            scopes=SCOPES,
            redirect_uri=self.redirect_uri,
        )

    def complete_sign_in(
        self, flow: dict[str, Any], response_parameters: dict[str, str]
    ) -> dict[str, str]:
        result = self.client.acquire_token_by_auth_code_flow(flow, response_parameters)
        if "error" in result:
            description = result.get("error_description", result["error"])
            raise RuntimeError(f"Microsoft Entra sign-in failed: {description}")

        claims = result.get("id_token_claims", {})
        object_id = claims.get("oid")
        display_name = claims.get("name")
        if not object_id or not display_name:
            raise RuntimeError("The ID token did not contain the oid and name claims")
        return {"object_id": str(object_id), "display_name": str(display_name)}