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

logger = logging.getLogger(__name__)

class OCIOutageEnergyLLM:
    """ Agent using OCI libraries to provide outage and energy information """

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain", "text/event-stream"]

    def __init__(self):
        self._agent = self._build_agent()
        self._user_id = "remote_llm"
        self._suggestion_out = SuggestionModel().build_suggestion_model()
        self._out_query = SUGGESTION_QUERY
        self._active_categories: list[str] = []

    def _build_agent(self) -> CompiledStateGraph:
        """Builds the LLM agent for the outage and energy agent."""
        oci_llm = ChatOCIGenAI(
            model_id="xai.grok-4-fast-non-reasoning",
            service_endpoint=os.getenv("SERVICE_ENDPOINT"),
            compartment_id=os.getenv("COMPARTMENT_ID"),
            model_kwargs={"temperature":0.7},
            auth_profile=os.getenv("AUTH_PROFILE"),
        )

        return create_agent(
            model=oci_llm,
            # tools=[get_outage_data, get_energy_data, get_industry_data],
            tools=[semantic_search, nl2sql_tool],
            system_prompt=MAIN_LLM_INSTRUCTIONS,
            name="outage_energy_llm",
            checkpointer= InMemorySaver()
        )
    
    async def oci_stream(self, query, session_id, categories: list[str] | None = None) -> AsyncIterable[dict[str, Any]]:
        """ Function to call agent and stream responses """

        self._active_categories = [str(c).strip() for c in (categories or []) if str(c).strip()]
        
        current_message = {"messages":[HumanMessage(query)]}
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
