import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("handler.py")
SPEC = importlib.util.spec_from_file_location("handler", MODULE_PATH)
handler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handler)


class HandlerTests(TestCase):
    def test_build_ug_api_key_uses_client_id_and_utc_hour(self):
        now = datetime(2026, 6, 4, 8, 30, tzinfo=timezone.utc)

        with patch.object(handler, "UG_CLIENT_ID", "4d0aefcf9016df5d"):
            self.assertEqual(
                handler.build_ug_api_key(now),
                "5e1e19946f01904b910b75c9574404f4",
            )

    def test_search_tabs_requests_chords_and_filters_results(self):
        response = {
            "tabs": [
                {"id": 1, "type": "Chords", "status": "approved"},
                {"id": 2, "type": "Tabs", "status": "approved"},
                {"id": 3, "type": "Chords", "status": "pending"},
            ]
        }

        with patch.object(handler, "fetch_ug_json", return_value=response) as fetch:
            self.assertEqual(handler.search_tabs("Creep", "Radiohead"), [response["tabs"][0]])

        fetch.assert_called_once_with(
            "/tab/search",
            [
                ("title", "Radiohead Creep"),
                ("page", 1),
                ("type[]", 300),
            ],
        )

    def test_get_tabs_uses_api_content_and_canonical_url(self):
        tab = {"id": 4169, "type": "Chords", "status": "approved"}
        tab_data = {
            "content": "[tab][ch]G[/ch] Creep[/tab]",
            "urlWeb": "https://tabs.ultimate-guitar.com/tab/radiohead/creep-chords-4169",
        }

        with patch.object(handler, "search_tabs", return_value=[tab]), patch.object(
            handler, "fetch_tab", return_value=tab_data
        ):
            results = handler.get_tabs("Creep", "Radiohead")

        self.assertEqual(results[0]["url"], tab_data["urlWeb"])
        self.assertIn('data-name="G"', results[0]["chords"])
