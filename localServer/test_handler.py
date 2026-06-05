from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import handler


class LocalServerHandlerTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.db_patch = patch.object(
            handler,
            "DB_PATH",
            Path(self.temp_dir.name) / "tabs.sqlite3",
        )
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_get_tab_page_urls_returns_empty_on_403(self):
        with patch.object(handler, "fetch_html", return_value=("blocked", 403)):
            self.assertEqual(handler.get_tab_page_urls("https://example.com/search"), [])

    def test_get_tab_page_urls_parses_ug_results(self):
        html = """
        <div class="js-store" data-content='{
            "store": {
                "page": {
                    "data": {
                        "results": [
                            {
                                "type": "Chords",
                                "tab_url": "https://tabs.ultimate-guitar.com/tab/radiohead/creep-chords-4169"
                            },
                            {
                                "type": "Tabs",
                                "tab_url": "https://tabs.ultimate-guitar.com/tab/radiohead/creep-tabs-123"
                            }
                        ]
                    }
                }
            }
        }'></div>
        """

        with patch.object(handler, "fetch_html", return_value=(html, 200)):
            self.assertEqual(
                handler.get_tab_page_urls("https://example.com/search"),
                ["https://tabs.ultimate-guitar.com/tab/radiohead/creep-chords-4169"],
            )

    def test_get_tabs_falls_back_to_ddg_when_ug_has_no_urls(self):
        with patch.object(handler, "get_tab_page_urls", return_value=[]), patch.object(
            handler,
            "get_tab_page_urls_ddg",
            return_value=["https://tabs.ultimate-guitar.com/tab/radiohead/creep-chords-4169"],
        ) as ddg, patch.object(handler, "scrape_tab_html", return_value="<section>tab</section>"):
            self.assertEqual(
                handler.get_tabs("Creep", "Radiohead"),
                [
                    {
                        "chords": "<section>tab</section>",
                        "url": "https://tabs.ultimate-guitar.com/tab/radiohead/creep-chords-4169",
                    }
                ],
            )

        ddg.assert_called_once_with("Creep", "Radiohead")

    def test_fetch_html_uses_cached_response(self):
        url = "https://example.com/cached"
        handler.cache_response(url, 200, "<html>cached</html>")

        with patch.object(handler.cf_requests, "get") as cf_get, patch.object(
            handler.SCRAPER, "get"
        ) as scraper_get:
            self.assertEqual(handler.fetch_html(url), ("<html>cached</html>", 200))

        cf_get.assert_not_called()
        scraper_get.assert_not_called()

    def test_fetch_html_caches_successful_network_response(self):
        class Response:
            text = "<html>fresh</html>"
            status_code = 200

        url = "https://example.com/fresh"
        with patch.object(handler.cf_requests, "get", return_value=Response()):
            self.assertEqual(handler.fetch_html(url), ("<html>fresh</html>", 200))

        self.assertEqual(
            handler.get_cached_response(url),
            {"status_code": 200, "body": "<html>fresh</html>"},
        )

    def test_fetch_html_does_not_cache_failed_response(self):
        class Response:
            text = "blocked"
            status_code = 403

        url = "https://example.com/blocked"
        with patch.object(handler.cf_requests, "get", return_value=Response()):
            self.assertEqual(handler.fetch_html(url), ("blocked", 403))

        self.assertIsNone(handler.get_cached_response(url))
