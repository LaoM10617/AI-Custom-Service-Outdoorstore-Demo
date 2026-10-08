"""Offline checks for exact fixture lookup and read-only demo boundaries."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agents.tools import DATA_DIR, after_sale_rule, query_order

orders = json.loads((DATA_DIR / "mock_orders.json").read_text(encoding="utf-8"))["orders"]
assert len(orders) == 6
assert len({order["status"] for order in orders}) == 6
for order in orders:
    answer = query_order("Please check " + order["order_id"].lower())
    assert order["order_id"] in answer and order["status"] in answer
    assert "ORDER |" in answer and "Read-only lookup" in answer
assert "provide" in query_order("Where is my order?")
assert "not found" in query_order("BH-9999")
assert "not found" in query_order("BH-10010")
assert "one order" in query_order("Compare BH-1001 with BH-1002")
assert "provide" in query_order("XBH-1001suffix")
assert "BH-1001" in query_order("BH-1001, please")
assert "cannot create tickets" in after_sale_rule("returns")
assert "30 days" in after_sale_rule("returns")
print("PASS: six fixtures, exact IDs, missing/unknown/multiple IDs, policy consistency")
