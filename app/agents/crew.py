# -*- coding: utf-8 -*-
"""Optional CrewAI workflow: classify a BlueHarbor request, then use support tools.
The framework manages execution; the separate animation is conceptual.
"""
from app.config import settings


def run_crew(message: str, history_text: str = "") -> str:
    from crewai import Agent, Crew, LLM, Process, Task

    from app.agents.tools import (
        after_sale_rule_tool,
        query_order_tool,
        search_knowledge_tool,
    )

    llm = LLM(
        model=f"openai/{settings.llm_model}",
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        temperature=0.3,
    )
    history_desc = f"\nConversation history:\n{history_text}" if history_text else ""

    router = Agent(
        role="Support request classifier",
        goal="Classify the customer request as knowledge, order or chat",
        backstory=("You classify support requests for BlueHarbor, a fictional outdoor retailer. "
                   "Return only JSON with intent (knowledge, order, or chat) and a brief English reason. Specific BH- order IDs and individual shipment or refund status use order; general policies use knowledge."),
        llm=llm,
        verbose=False,
    )

    executive = Agent(
        role="BlueHarbor support specialist",
        goal="Use the appropriate tools and give concise, grounded English support answers",
        backstory=("You support BlueHarbor customers using order, knowledge and policy tools. "
                   "Use only tool evidence. Use neutral business wording. These are local sample records, not live Shopify data; answer truthfully if asked about their provenance. Ask for missing order IDs. Never invent records or claim to refund, cancel, notify staff or create a ticket."),
        tools=[search_knowledge_tool, query_order_tool, after_sale_rule_tool],
        llm=llm,
        verbose=False,
    )

    task_router = Task(
        description=f"Classify this customer message: {message} (use conversation history when relevant){history_desc}. Return only intent JSON.",
        expected_output="JSON: intent / reason",
        agent=router,
    )
    task_exec = Task(
        description=(
            "Handle the customer message using the classifier result. Rules: "
            "For knowledge, call search_knowledge. "
            "For order, call query_order with the customer message and exact order ID. "
            "For returns policies, call after_sale_rule. "
            "For chat, respond politely. "
            "Use conversation history for continuity. "
            "Give the customer a complete English answer. "
            f"{history_desc}"
        ),
        expected_output="Final English customer response",
        agent=executive,
    )

    crew = Crew(
        agents=[router, executive],
        tasks=[task_router, task_exec],
        process=Process.sequential,
        verbose=False,
    )
    result = crew.kickoff()
    return str(getattr(result, "raw", result))
