import unittest
from unittest.mock import MagicMock, patch

from auth import EntraAuth, SCOPES


class EntraAuthTests(unittest.TestCase):
    @patch("auth.msal.PublicClientApplication")
    def test_begins_authorization_code_flow_with_redirect_uri(
        self, application_factory: MagicMock
    ) -> None:
        application = application_factory.return_value
        application.initiate_auth_code_flow.return_value = {
            "auth_uri": "https://login.microsoftonline.com/example/oauth2/v2.0/authorize"
        }
        auth = EntraAuth(
            "client-id",
            "tenant-id",
            "http://localhost:5000/auth/callback",
        )

        flow = auth.begin_sign_in()

        self.assertIn("auth_uri", flow)
        application.initiate_auth_code_flow.assert_called_once_with(
            scopes=SCOPES,
            redirect_uri="http://localhost:5000/auth/callback",
        )

    @patch("auth.msal.PublicClientApplication")
    def test_completes_sign_in_with_identity_claims(
        self, application_factory: MagicMock
    ) -> None:
        application_factory.return_value.acquire_token_by_auth_code_flow.return_value = {
            "id_token_claims": {
                "oid": "00000000-0000-0000-0000-000000000001",
                "name": "Workshop Participant",
            }
        }
        auth = EntraAuth("client-id", "tenant-id", "http://localhost/callback")

        user = auth.complete_sign_in({"state": "state"}, {"code": "code"})

        self.assertEqual(user["display_name"], "Workshop Participant")
        self.assertEqual(
            user["object_id"], "00000000-0000-0000-0000-000000000001"
        )

    @patch("auth.msal.PublicClientApplication")
    def test_surfaces_sign_in_errors(self, application_factory: MagicMock) -> None:
        application_factory.return_value.acquire_token_by_auth_code_flow.return_value = {
            "error": "access_denied",
            "error_description": "The user cancelled sign-in.",
        }
        auth = EntraAuth("client-id", "tenant-id", "http://localhost/callback")

        with self.assertRaisesRegex(RuntimeError, "user cancelled"):
            auth.complete_sign_in({"state": "state"}, {"error": "access_denied"})


if __name__ == "__main__":
    unittest.main()