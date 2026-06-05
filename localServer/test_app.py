from unittest import TestCase
from unittest.mock import patch

import app


class LocalServerAppTests(TestCase):
    def test_onug_requires_query_params(self):
        client = app.app.test_client()

        response = client.get("/onug?artist=Radiohead")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"error": "artist and song are required"},
        )

    def test_onug_returns_boolean_and_cache_header(self):
        client = app.app.test_client()

        with patch.object(app.handler, "is_in_ultimate_guitar", return_value=True) as onug:
            response = client.get("/onug?artist=Radiohead&song=Creep")

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.get_json(), True)
        self.assertEqual(response.headers["Cache-Control"], "max-age=604800")
        onug.assert_called_once_with("Creep", "Radiohead")
