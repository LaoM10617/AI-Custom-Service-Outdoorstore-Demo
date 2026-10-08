"""BlueHarbor tools: grounded knowledge answers and read-only simulated orders."""
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def search_knowledge(query: str) -> str:
    """Answer a BlueHarbor product or policy question using the knowledge base."""
    from app.rag.retriever import answer_with_rag, build_llm
    answer, _ = answer_with_rag(query, build_llm())
    return answer


def query_order(message: str) -> str:
    """Read one simulated order by its exact BH-1001 style identifier; never modify it."""
    ids = re.findall(r"(?<![A-Za-z0-9])BH-\d+(?![A-Za-z0-9])", message.upper())
    ids = list(dict.fromkeys(ids))
    if not ids:
        return "Please provide a BlueHarbor order ID, for example BH-1001."
    if len(ids) > 1:
        return "Please ask about one order at a time."
    data = json.loads((DATA_DIR / "mock_orders.json").read_text(encoding="utf-8"))
    order = next((item for item in data["orders"] if item["order_id"] == ids[0]), None)
    if order is None:
        return f"Order {ids[0]} was not found in the available records. Please check the ID."
    return (
        f"ORDER | Snapshot: {order['snapshot_date']} | {order['order_id']}\n"
        f"Item: {order['product']} ({order['sku']}) | Quantity: {order['quantity']}\n"
        f"Total: {order['currency']} {order['total']}\n"
        f"Status: {order['status']} | Payment: {order['payment_status']} | "
        f"Fulfillment: {order['fulfillment_status']} | Refund: {order['refund_status']}\n"
        f"Tracking: {order['tracking_number'] or 'Not available'}\n{order['note']}\n"
        "Read-only lookup: this lookup does not cancel, refund, or change an order."
    )


def after_sale_rule(_message: str) -> str:
    """Read the fictional BlueHarbor returns policy; this tool performs no actions."""
    text = (DATA_DIR / "knowledge_base.md").read_text(encoding="utf-8")
    return text.split("## Returns and damaged items\n", 1)[1].split("\n## ", 1)[0].strip()


search_knowledge_tool = None
query_order_tool = None
after_sale_rule_tool = None
CREW_TOOLS_READY = False
try:
    from crewai.tools import tool
    search_knowledge_tool = tool("search_knowledge")(search_knowledge)
    query_order_tool = tool("query_order")(query_order)
    after_sale_rule_tool = tool("after_sale_rule")(after_sale_rule)
    CREW_TOOLS_READY = True
except Exception:  # CrewAI remains an optional integration.
    CREW_TOOLS_READY = False
