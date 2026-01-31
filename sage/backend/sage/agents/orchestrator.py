"""
Sage Orchestrator - Layer 3 of the Agent Architecture.

The Sage Orchestrator is the "brain" that:
- Interprets user intent
- Routes requests to appropriate sub-agents
- Aggregates results into coherent responses
- Maintains conversation context
- Enforces human-in-the-loop policies

See sage-agent-architecture.md Section 4 for specifications.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic

from .base import BaseAgent, AgentResult, SearchContext
from .foundational.search import SearchAgent
from .foundational.indexer import IndexerAgent
from sage.services.data_layer.service import DataLayerService
from sage.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A message in the conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class PendingApproval:
    """An action awaiting user approval."""
    id: str
    agent: str
    action: str
    description: str
    context: dict = field(default_factory=dict)


@dataclass
class IntentAnalysis:
    """Result of analyzing user intent from a message."""
    primary_intent: str  # ChatIntent value as string
    secondary_intents: list[str] = field(default_factory=list)
    entity_hints: list[str] = field(default_factory=list)
    requires_action: bool = False  # True for draft/send/schedule
    confidence: float = 1.0
    clarification_needed: str | None = None
    is_complex: bool = False  # True if Claude analysis was used


@dataclass
class ExecutionPlan:
    """Plan for executing a user request."""
    intent: str
    agents_to_invoke: list[tuple[str, str]]  # List of (agent_name, capability)
    is_parallel: bool = False
    params: dict = field(default_factory=dict)
    requires_clarification: bool = False
    clarification_question: str | None = None
    entity_hints: list[str] = field(default_factory=list)


@dataclass
class OrchestratorResponse:
    """Response from the orchestrator to a user message."""
    text: str
    agent_results: list[AgentResult] = field(default_factory=list)
    pending_approvals: list[PendingApproval] = field(default_factory=list)
    conversation_id: str | None = None


# Intent to capability mapping
# Maps intent types to list of (agent_name, capability) tuples
INTENT_CAPABILITIES = {
    "email": [("search", "search_for_task")],
    "followup": [("search", "search_for_task")],
    "meeting": [("search", "search_for_task")],
    "contact": [("search", "search_for_task")],
    "todo": [("search", "search_for_task")],
    "general": [("search", "search_for_task")],
}

# Action keywords that indicate the user wants to DO something (not just query)
ACTION_KEYWORDS = [
    r"\bdraft\b", r"\bsend\b", r"\bschedule\b", r"\bcreate\b",
    r"\bremind\b", r"\bset up\b", r"\bbook\b", r"\bcancel\b",
    r"\bdelete\b", r"\bupdate\b", r"\bchange\b", r"\bmodify\b",
]


class SageOrchestrator:
    """
    The Sage Orchestrator coordinates all agent activity and
    manages user interaction.

    This is the main entry point for the chat API.
    """

    def __init__(
        self,
        data_layer: DataLayerService,
        claude_client: AsyncAnthropic | None = None,
    ):
        """
        Initialize the orchestrator with all agents.

        Args:
            data_layer: The data layer service for database access
            claude_client: Optional Anthropic client (created if not provided)
        """
        self.data_layer = data_layer
        self.settings = get_settings()

        # Initialize Claude client
        if claude_client:
            self.claude = claude_client
        else:
            self.claude = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

        # Foundational agents
        self.search_agent = SearchAgent(data_layer)
        self.indexer_agent = IndexerAgent(data_layer)

        # Task agents registry (for future expansion)
        self.agents: dict[str, BaseAgent] = {
            "search": self.search_agent,
            "indexer": self.indexer_agent,
        }

        # Conversation state
        self.conversation_history: list[Message] = []
        self.pending_approvals: list[PendingApproval] = []
        self.conversation_id: str | None = None

    async def process_message(self, user_message: str) -> OrchestratorResponse:
        """
        Main entry point for user interaction.

        This method:
        1. Adds message to conversation history
        2. Analyzes intent (hybrid regex + Claude if complex)
        3. Plans execution (maps intent to agents)
        4. Executes the plan (calls agents for context)
        5. Formats response using Claude with context
        6. Indexes conversation turn for future memory

        Args:
            user_message: The user's message

        Returns:
            OrchestratorResponse with the assistant's response
        """
        logger.info(f"Orchestrator processing message: {user_message[:100]}...")

        # 1. Add to conversation history
        self.conversation_history.append(
            Message(role="user", content=user_message)
        )

        # 2. Analyze intent
        intent_analysis = await self._analyze_intent(user_message)
        logger.info(
            f"Intent analysis: primary={intent_analysis.primary_intent}, "
            f"confidence={intent_analysis.confidence:.2f}, "
            f"requires_action={intent_analysis.requires_action}"
        )

        # 3. Plan execution
        execution_plan = await self._plan_execution(user_message, intent_analysis)

        # 4. Execute plan (get context from agents)
        results = await self._execute_plan(execution_plan)

        # 5. Format response using Claude with retrieved context
        response = await self._format_response(user_message, results, execution_plan)

        # 6. Add response to history
        self.conversation_history.append(
            Message(role="assistant", content=response.text)
        )

        # 7. Index conversation turn for future memory (fire and forget)
        try:
            await self._index_conversation_turn(user_message, response.text, results)
        except Exception as e:
            logger.warning(f"Failed to index conversation turn: {e}")

        return response

    async def approve_action(self, approval_id: str) -> OrchestratorResponse:
        """
        User approves a pending action.

        Args:
            approval_id: ID of the pending approval

        Returns:
            OrchestratorResponse with result of the approved action
        """
        # Find the pending approval
        approval = next(
            (a for a in self.pending_approvals if a.id == approval_id),
            None
        )
        if not approval:
            return OrchestratorResponse(
                text=f"Approval {approval_id} not found or already processed.",
                conversation_id=self.conversation_id
            )

        # TODO: Execute the approved action
        # This will be implemented in Phase 4.2 when task agents are ready

        # Remove from pending
        self.pending_approvals = [
            a for a in self.pending_approvals if a.id != approval_id
        ]

        return OrchestratorResponse(
            text=f"Action approved: {approval.description}. Execution pending implementation.",
            conversation_id=self.conversation_id
        )

    async def reject_action(
        self, approval_id: str, reason: str | None = None
    ) -> OrchestratorResponse:
        """
        User rejects a pending action.

        Args:
            approval_id: ID of the pending approval
            reason: Optional reason for rejection

        Returns:
            OrchestratorResponse acknowledging the rejection
        """
        # Find and remove the pending approval
        approval = next(
            (a for a in self.pending_approvals if a.id == approval_id),
            None
        )
        if not approval:
            return OrchestratorResponse(
                text=f"Approval {approval_id} not found or already processed.",
                conversation_id=self.conversation_id
            )

        self.pending_approvals = [
            a for a in self.pending_approvals if a.id != approval_id
        ]

        reason_text = f" Reason: {reason}" if reason else ""
        return OrchestratorResponse(
            text=f"Action rejected: {approval.description}.{reason_text}",
            conversation_id=self.conversation_id
        )

    async def _analyze_intent(self, user_message: str) -> IntentAnalysis:
        """
        Analyze user intent using hybrid approach.

        1. Use fast regex-based detection for simple queries
        2. Use Claude for complex/ambiguous cases

        Complexity heuristics:
        - Long messages (>100 chars)
        - Multi-part requests (contains "and", "also", "then")
        - Action keywords (draft, send, schedule)
        - Ambiguous patterns
        """
        # Import intent detection from chat.py to reuse existing logic
        from sage.api.chat import detect_chat_intent, extract_entity_hints, ChatIntent

        # Fast path: regex-based detection
        primary_intent = detect_chat_intent(user_message)
        entity_hints = extract_entity_hints(user_message)

        # Check for action keywords
        message_lower = user_message.lower()
        requires_action = any(
            re.search(pattern, message_lower)
            for pattern in ACTION_KEYWORDS
        )

        # Determine if this is a complex query requiring Claude analysis
        is_complex = (
            len(user_message) > 150 or
            bool(re.search(r"\b(and|also|then|first|after|before)\b", message_lower)) or
            requires_action or
            user_message.count("?") > 1
        )

        # For now, use fast path confidence
        # In the future, could use Claude to refine for complex cases
        confidence = 0.9 if not is_complex else 0.7

        return IntentAnalysis(
            primary_intent=primary_intent.value,
            secondary_intents=[],
            entity_hints=entity_hints,
            requires_action=requires_action,
            confidence=confidence,
            is_complex=is_complex,
        )

    async def _plan_execution(
        self, user_message: str, intent_analysis: IntentAnalysis
    ) -> ExecutionPlan:
        """
        Map analyzed intent to agent capabilities.

        Determines which agents need to be invoked and in what order.
        """
        intent = intent_analysis.primary_intent
        agents_to_invoke = INTENT_CAPABILITIES.get(intent, [("search", "search_for_task")])

        return ExecutionPlan(
            intent=intent,
            agents_to_invoke=agents_to_invoke,
            is_parallel=False,  # Sequential by default
            params={
                "task_description": user_message,
                "entity_hints": intent_analysis.entity_hints,
            },
            entity_hints=intent_analysis.entity_hints,
        )

    async def _execute_plan(self, plan: ExecutionPlan) -> list[AgentResult]:
        """
        Execute the planned agent invocations.

        Currently supports sequential execution. Parallel execution
        will be added in Phase 4.2.
        """
        results = []

        for agent_name, capability in plan.agents_to_invoke:
            if agent_name not in self.agents:
                logger.warning(f"Agent '{agent_name}' not registered")
                continue

            agent = self.agents[agent_name]

            try:
                # Map intent to requesting_agent for context enrichment
                intent_to_agent = {
                    "email": "chat_email",
                    "followup": "chat_followup",
                    "meeting": "chat_meeting",
                    "contact": "chat_contact",
                    "todo": "chat_todo",
                    "general": "chat",
                }
                requesting_agent = intent_to_agent.get(plan.intent, "chat")

                result = await agent.execute(
                    capability=capability,
                    params={
                        "requesting_agent": requesting_agent,
                        "task_description": plan.params.get("task_description", ""),
                        "entity_hints": plan.entity_hints,
                        "max_results": 15,
                    }
                )
                results.append(result)

                logger.info(
                    f"Agent '{agent_name}.{capability}' completed: "
                    f"success={result.success}"
                )

            except Exception as e:
                logger.error(f"Agent '{agent_name}' execution failed: {e}")
                results.append(AgentResult(
                    success=False,
                    data={},
                    errors=[f"Agent execution failed: {str(e)}"]
                ))

        return results

    async def _format_response(
        self, user_message: str, results: list[AgentResult], plan: ExecutionPlan
    ) -> OrchestratorResponse:
        """
        Format agent results into a user-facing response using Claude.

        Sends the user message along with retrieved context to Claude
        for a grounded, accurate response.
        """
        # Extract context from results
        context = None
        for result in results:
            if result.success and "context" in result.data:
                context = result.data["context"]
                break

        # Format context for Claude
        from sage.api.chat import format_search_context
        formatted_context = format_search_context(context) if context else {
            "instructions": "No context was retrieved. If the user asks about specific data, explain that you don't have access to that information right now."
        }

        # Build system prompt
        system_prompt = self._build_system_prompt(formatted_context, plan)

        # Build messages including conversation history
        messages = []
        # Include recent conversation history for context
        for msg in self.conversation_history[-5:]:  # Last 5 messages
            messages.append({
                "role": msg.role,
                "content": msg.content
            })

        try:
            response = await self.claude.messages.create(
                model=self.settings.claude_model,
                max_tokens=2048,
                system=system_prompt,
                messages=messages
            )

            response_text = response.content[0].text

        except Exception as e:
            logger.error(f"Claude response generation failed: {e}")
            response_text = (
                "I apologize, but I encountered an error generating a response. "
                "Please try again."
            )

        return OrchestratorResponse(
            text=response_text,
            agent_results=results,
            pending_approvals=self.pending_approvals.copy(),
            conversation_id=self.conversation_id
        )

    def _build_system_prompt(self, context: dict, plan: ExecutionPlan) -> str:
        """Build the system prompt for Claude with context."""
        base_prompt = """You are Sage, a helpful AI assistant for managing email, calendar, follow-ups, and tasks.

You have access to the user's actual data retrieved from their accounts. Use ONLY this data when answering questions about their emails, contacts, follow-ups, meetings, or past conversations.

IMPORTANT RULES:
1. Never hallucinate or make up data that isn't in the context
2. If information isn't available, say so clearly
3. Display times in Eastern Time (ET) format
4. Be concise but helpful
5. When showing emails or follow-ups, include key details like sender, subject, and date

"""
        # Add context section
        context_section = "\n--- Retrieved Context ---\n"
        if context:
            import json
            # Remove instructions key for cleaner context
            ctx_copy = {k: v for k, v in context.items() if k != "instructions"}
            context_section += json.dumps(ctx_copy, indent=2, default=str)
        else:
            context_section += "No context available."

        # Add instructions from context if present
        instructions = context.get("instructions", "") if context else ""
        if instructions:
            context_section += f"\n\n{instructions}"

        return base_prompt + context_section

    async def _index_conversation_turn(
        self,
        user_message: str,
        response_text: str,
        results: list[AgentResult]
    ) -> None:
        """
        Index this conversation turn for future memory retrieval.

        Uses the IndexerAgent to persist the conversation exchange
        and extract any facts, decisions, or preferences.
        """
        if not self.conversation_id:
            logger.debug("No conversation_id, skipping memory indexing")
            return

        try:
            result = await self.indexer_agent.execute(
                "index_memory",
                {
                    "conversation_id": self.conversation_id,
                    "user_message": user_message,
                    "sage_response": response_text,
                    "turn_number": len(self.conversation_history) // 2,
                    "extract_facts": True,
                }
            )

            if result.success:
                facts_count = result.data.get("facts_extracted", 0)
                logger.info(
                    f"Indexed conversation turn for {self.conversation_id}, "
                    f"{facts_count} facts extracted"
                )
            else:
                logger.warning(f"Failed to index conversation: {result.errors}")

        except Exception as e:
            logger.warning(f"Error indexing conversation turn: {e}")

    def register_agent(self, agent: BaseAgent) -> None:
        """Register a task agent with the orchestrator."""
        self.agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")

    def set_conversation_id(self, conversation_id: str) -> None:
        """Set the current conversation ID for memory tracking."""
        self.conversation_id = conversation_id
        self.conversation_history = []
        self.pending_approvals = []
