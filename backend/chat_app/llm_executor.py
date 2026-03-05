import logging
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    DataPart,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_parts_message,
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError
from chat_app.main_llm import OCIOutageEnergyLLM

logger = logging.getLogger(__name__)


class OutageEnergyLLMExecutor(AgentExecutor):
    """Outage and Energy LLM executor Example."""

    def __init__(self):
        self.oci_ui_agent = OCIOutageEnergyLLM()
        self.oci_text_agent = OCIOutageEnergyLLM()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        query = ""

        logger.info(
            f"--- Client requested extensions: {context.requested_extensions} ---"
        )

        # Determine which agent to use based on whether the a2ui extension is active.
        agent = self.oci_text_agent

        session_id = None
        if context.message and context.message.parts:
            logger.info(
                f"--- AGENT_EXECUTOR: Processing {len(context.message.parts)} message parts ---"
            )
            for i, part in enumerate(context.message.parts):
                if isinstance(part.root, DataPart):
                    if "userAction" in part.root.data:
                        logger.info(f"  Part {i}: Found a2ui UI ClientEvent payload.")
                        ui_event_part = part.root.data["userAction"]
                    elif "request" in part.root.data:
                        logger.info(f"  Part {i}: Found request in DataPart.")
                        query = part.root.data["request"]
                        # Extract session ID from metadata
                        if "metadata" in part.root.data and "sessionId" in part.root.data["metadata"]:
                            session_id = part.root.data["metadata"]["sessionId"]
                            logger.info(f"  Part {i}: Found sessionId in metadata: {session_id}")
                    else:
                        logger.info(f"  Part {i}: DataPart (data: {part.root.data})")
                elif isinstance(part.root, TextPart):
                    logger.info(f"  Part {i}: TextPart (text: {part.root.text})")
                    if not query:
                        query = part.root.text
                else:
                    logger.info(f"  Part {i}: Unknown part type ({type(part.root)})")

        if not query:
            logger.info("No a2ui UI event part found. Falling back to text input.")
            query = context.get_user_input()

        logger.info(f"--- AGENT_EXECUTOR: Final query for LLM: '{query}' ---")

        task = context.current_task

        if not task:
            task = new_task(context.message)
            await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        memory_id = session_id if session_id else task.context_id
        logger.info(f"--- AGENT_EXECUTOR: Using memory ID: {memory_id} ---")

        async for item in agent.oci_stream(query, memory_id):
            is_task_complete = item["is_task_complete"]
            if not is_task_complete:
                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(item["updates"], task.context_id, task.id),
                )
                continue
            
            content = item["content"]
            final_parts = []
            final_parts.append(Part(root=TextPart(text=content.strip())))

            final_state = item['final_state']
            final_parts.append(Part(root=TextPart(text=final_state.strip())))

            final_token_count = item['token_count']
            final_parts.append(Part(root=TextPart(text=final_token_count.strip())))

            suggestions = item['suggestions']
            final_parts.append(Part(root=TextPart(text=suggestions.strip())))

            logger.info("--- FINAL PARTS TO BE SENT ---")
            for i, part in enumerate(final_parts):
                logger.info(f"  - Part {i}: Type = {type(part.root)}")
                if isinstance(part.root, TextPart):
                    logger.info(f"    - Text: {part.root.text[:200]}...")
                elif isinstance(part.root, DataPart):
                    logger.info(f"    - Data: {str(part.root.data)[:200]}...")
            logger.info("-----------------------------")

            final_state = TaskState.completed

            await updater.update_status(
                final_state,
                new_agent_parts_message(final_parts, task.context_id, task.id),
                final=True,
            )
            break

    async def cancel(
        self, request: RequestContext, event_queue: EventQueue
    ) -> Task | None:
        raise ServerError(error=UnsupportedOperationError())
