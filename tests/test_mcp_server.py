from __future__ import annotations

import unittest


class McpServerImportTests(unittest.TestCase):
    def test_mcp_server_imports_and_exposes_expected_tools(self) -> None:
        import mcp_server

        tool_names = {t.name for t in mcp_server.mcp._tool_manager.list_tools()}
        expected = {
            "get_price",
            "get_balances",
            "get_signal",
            "place_market_buy",
            "place_market_sell",
            "place_limit_buy",
            "place_limit_sell",
            "get_open_orders",
            "run_dca",
        }
        self.assertEqual(tool_names, expected)


if __name__ == "__main__":
    unittest.main()
