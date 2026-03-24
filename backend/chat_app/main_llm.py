import logging
import os
from collections.abc import AsyncIterable
from typing import Any
from langchain.agents import create_agent
from langchain_oci import ChatOCIGenAI
from langchain.messages import HumanMessage, AIMessage, AnyMessage, ToolMessage
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from core.chat_app.prompts import MAIN_LLM_INSTRUCTIONS
from core.common_struct import SuggestionModel
from core.common_struct import SuggestedQuestions
from core.common_struct import SUGGESTION_QUERY
from chat_app.rag_tool import semantic_search
from chat_app.nl2sql_tool import nl2sql_tool
from chat_app.data_tools import get_outage_data, get_energy_data, get_industry_data
from chat_app.model_registry import DEFAULT_CHAT_MODEL

logger = logging.getLogger(__name__)


def _coerce_history_messages(history: list[dict[str, Any]] | None) -> list[AnyMessage]:
    coerced: list[AnyMessage] = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if role == "assistant":
            coerced.append(AIMessage(content=content))
        elif role == "user":
            coerced.append(HumanMessage(content=content))
    return coerced


def _build_oci_chat_model(model_id: str = DEFAULT_CHAT_MODEL) -> ChatOCIGenAI:
    model_kwargs: dict[str, Any] = {}
    configured_temperature = os.getenv("CHAT_MODEL_TEMPERATURE")
    if configured_temperature not in (None, ""):
        try:
            model_kwargs["temperature"] = float(configured_temperature)
        except ValueError:
            logger.warning(
                "Ignoring invalid CHAT_MODEL_TEMPERATURE=%s; using provider defaults",
                configured_temperature,
            )

    logger.info(
        "Creating OCI chat model client: model_id=%s model_kwargs=%s",
        model_id,
        model_kwargs,
    )

    return ChatOCIGenAI(
        model_id=model_id,
        service_endpoint=os.getenv("SERVICE_ENDPOINT"),
        compartment_id=os.getenv("COMPARTMENT_ID"),
        model_kwargs=model_kwargs,
        auth_profile=os.getenv("AUTH_PROFILE"),
    )

class KnowledgeAssistantAgent:
    """General-purpose knowledge assistant backed by OCI GenAI and retrieval tools."""

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain", "text/event-stream"]

    def __init__(self, model_id: str = DEFAULT_CHAT_MODEL):
        self._model_id = model_id
        self._agent = self._build_agent()
        self._user_id = "remote_llm"
        self._suggestion_out = SuggestionModel().build_suggestion_model()
        self._out_query = SUGGESTION_QUERY
        self._active_categories: list[str] = []

    def _build_agent(self) -> CompiledStateGraph:
        """Build the general-purpose assistant agent."""
        oci_llm = _build_oci_chat_model(self._model_id)

        return create_agent(
            model=oci_llm,
            # tools=[get_outage_data, get_energy_data, get_industry_data],
            tools=[semantic_search, nl2sql_tool],
            system_prompt=MAIN_LLM_INSTRUCTIONS,
            name="knowledge_assistant_agent",
            checkpointer= InMemorySaver()
        )
    
    async def oci_stream(self, query, session_id, categories: list[str] | None = None, history: list[dict[str, Any]] | None = None) -> AsyncIterable[dict[str, Any]]:
        """ Function to call agent and stream responses """

        self._active_categories = [str(c).strip() for c in (categories or []) if str(c).strip()]

        prior_messages = _coerce_history_messages(history)
        current_message = {"messages": [*prior_messages, HumanMessage(query)]}
        config:RunnableConfig = {"run_id":str(session_id), "configurable": {"thread_id": str(session_id)}}
        final_response_content = None
        final_model_state = None
        model_token_count = 0
        last_emitted_text = ""

        async for event in self._agent.astream(
            input=current_message,
            stream_mode="values",
            config=config
        ):
            latest_update:AnyMessage = event['messages'][-1]
            final_response_content = getattr(latest_update, "content", None)

            # If the model is producing text, stream the delta so the UI updates fast.
            if isinstance(latest_update, AIMessage):
                full_text = str(latest_update.content or "")
                if full_text.startswith(last_emitted_text):
                    delta = full_text[len(last_emitted_text):]
                else:
                    delta = full_text
                if delta:
                    last_emitted_text = full_text
                    yield {
                        "type": "delta",
                        "is_task_complete": False,
                        "delta": delta,
                    }

            # Emit ONLY tool-related status events (so normal chat doesn't show noisy "processing" logs).
            if hasattr(latest_update, 'tool_calls') and latest_update.tool_calls:
                if len(latest_update.tool_calls) == 1:
                    tool_name = str(latest_update.tool_calls[0].get('name'))
                    tool_args = str(latest_update.tool_calls[0].get('args'))
                    yield {
                        "type": "status",
                        "is_task_complete": False,
                        "updates": f"Model calling tool: {tool_name} with args {tool_args}",
                    }
                else:
                    tool_names = [str(tc.get('name', '')) for tc in latest_update.tool_calls]
                    yield {
                        "type": "status",
                        "is_task_complete": False,
                        "updates": f"Model called tools: {', '.join(tool_names)}",
                    }
            elif isinstance(latest_update, ToolMessage):
                tool_name = str(latest_update.name)
                status_content = str(latest_update.content)
                yield {
                    "type": "status",
                    "is_task_complete": False,
                    "updates": f"Tool {tool_name} responded with:\n{status_content}",
                }
            elif isinstance(latest_update, AIMessage):
                metadata = getattr(latest_update, "response_metadata", {}) or {}
                total_tokens_raw = metadata.get("total_tokens")
                try:
                    total_tokens_on_call = int(total_tokens_raw) if total_tokens_raw is not None else 0
                except (TypeError, ValueError):
                    total_tokens_on_call = 0
                model_token_count = model_token_count + total_tokens_on_call

                # Keep optional final state info (not streamed) for debugging.
                model_id = str(metadata.get("model_id"))
                agent_name = str(latest_update.name)
                final_model_state = f"model_id: {model_id}, agent_name: {agent_name}, total_tokens: {str(model_token_count)}"

        suggestions = await self._suggestion_out.ainvoke(self._out_query+f"\n\nContext for question generation:\n{final_response_content}")
        if not suggestions: suggestions = SuggestedQuestions(suggested_questions=["Tell me more details about first data", "Make a summary of data given"])
        
        yield {
            "type": "final",
            "is_task_complete": True,
            "content": f"{final_response_content}",
            "final_state": f"{final_model_state}",
            "token_count": str(model_token_count),
            "suggestions": suggestions.model_dump_json()
        }


# Backward-compatible alias for existing imports.
OCIOutageEnergyLLM = KnowledgeAssistantAgent


async def stream_augmented_response(
    query: str,
    model_id: str = DEFAULT_CHAT_MODEL,
) -> AsyncIterable[str]:
    """Stream plain text directly from the OCI chat model for an already-augmented prompt."""

    llm = _build_oci_chat_model(model_id=model_id)
    emitted_text = ""
    async for chunk in llm.astream([HumanMessage(query)]):
        text = getattr(chunk, "content", "")
        if isinstance(text, list):
            text = "".join(str(part) for part in text if part is not None)
        text_value = str(text or "")
        if not text_value:
            continue

        if text_value.startswith(emitted_text):
            delta = text_value[len(emitted_text):]
        else:
            delta = text_value

        if not delta:
            continue

        emitted_text = text_value
        yield delta
