# Sage Agent Architecture: Orchestrator

**Part of:** [Sage Architecture Documentation](00-overview.md)

---

## Layer 3: Sage Orchestrator

The Sage Orchestrator is the "brain" that interprets user intent, coordinates sub-agents, and maintains conversation coherence.

### Orchestrator Responsibilities

1. **Intent Recognition** — Understand what the user wants
2. **Agent Selection** — Choose which sub-agent(s) to invoke
3. **Context Coordination** — Ensure agents have what they need
4. **Result Aggregation** — Combine outputs into coherent response
5. **Conversation Management** — Maintain multi-turn context
6. **Policy Enforcement** — Apply human-in-the-loop rules
7. **Error Handling** — Gracefully handle agent failures

---

## Orchestrator Specification

```yaml
orchestrator:
  name: sage
  layer: orchestrator

responsibilities:
  - Interpret user messages
  - Route to appropriate agents
  - Manage multi-agent workflows
  - Maintain conversation history
  - Enforce approval policies
  - Format responses for user

conversation_context:
  - User profile and preferences
  - Current conversation history
  - Pending approvals
  - Active multi-step workflows
  - Recent agent results cache

routing_logic:
  - Single-agent tasks: Route directly
  - Multi-agent tasks: Coordinate sequence or parallel execution
  - Ambiguous requests: Ask for clarification
  - Complex workflows: Break into steps, track progress
```

---

## Orchestrator Implementation

```python
class SageOrchestrator:
    """
    The Sage Orchestrator coordinates all agent activity and
    manages user interaction.
    """

    def __init__(self):
        # Initialize agents
        self.search_agent = SearchAgent()
        self.indexer_agent = IndexerAgent()

        self.agents: dict[str, BaseAgent] = {
            "email": EmailAgent(self.search_agent, self.indexer_agent),
            "followup": FollowUpAgent(self.search_agent, self.indexer_agent),
            "meeting": MeetingAgent(self.search_agent, self.indexer_agent),
            "calendar": CalendarAgent(self.search_agent, self.indexer_agent),
            "briefing": BriefingAgent(self.search_agent, self.indexer_agent),
            "draft": DraftAgent(self.search_agent, self.indexer_agent),
            "property": PropertyAgent(self.search_agent, self.indexer_agent),
            "research": ResearchAgent(self.search_agent, self.indexer_agent),
        }

        self.conversation_history: list[Message] = []
        self.pending_approvals: list[PendingApproval] = []
        self.conversation_id: str = None  # Set per session

    async def process_message(self, user_message: str) -> OrchestratorResponse:
        """
        Main entry point for user interaction.
        """
        # 1. Add to conversation history
        self.conversation_history.append(Message(role="user", content=user_message))

        # 2. Retrieve relevant memories before processing
        memories = await self.search_agent.get_relevant_memories(
            query=user_message,
            conversation_id=self.conversation_id
        )

        # 3. Analyze intent and plan execution (with memory context)
        execution_plan = await self._plan_execution(user_message, memories)

        # 4. Execute plan (may involve multiple agents)
        results = await self._execute_plan(execution_plan)

        # 5. Aggregate results into response
        response = await self._format_response(results, execution_plan)

        # 6. Add response to history
        self.conversation_history.append(Message(role="assistant", content=response.text))

        # 7. Index this conversation turn for future memory
        await self._index_conversation_turn(user_message, response.text, results)

        return response

    async def _index_conversation_turn(
        self,
        user_message: str,
        sage_response: str,
        results: list[AgentResult]
    ) -> None:
        """
        Index the conversation exchange for persistent memory.
        Extracts facts, decisions, and preferences automatically.
        """
        await self.indexer_agent.execute(
            capability="index_memory",
            params={
                "conversation_id": self.conversation_id,
                "turn_number": len(self.conversation_history) // 2,
                "user_message": user_message,
                "sage_response": sage_response,
                "agent_results": [r.data for r in results],
                "extract_facts": True,  # Auto-extract facts/decisions/preferences
            }
        )

    async def _plan_execution(self, user_message: str) -> ExecutionPlan:
        """
        Use Claude to analyze intent and create execution plan.
        """
        planning_prompt = f"""
        Analyze this user message and create an execution plan.

        User message: {user_message}

        Available agents and their capabilities:
        {self._get_agent_descriptions()}

        Recent conversation context:
        {self._get_recent_context()}

        Respond with:
        1. Primary intent (what does user want?)
        2. Required agents (which agents needed?)
        3. Execution order (parallel or sequential?)
        4. Context requirements (what context to gather?)
        5. Clarification needed? (any ambiguity?)
        """

        plan = await self._call_claude(planning_prompt, response_format=ExecutionPlan)
        return plan

    async def _execute_plan(self, plan: ExecutionPlan) -> list[AgentResult]:
        """
        Execute the planned agent calls.
        """
        results = []

        # First, gather context via Search Agent
        context = await self.search_agent.search_for_task(
            requesting_agent="orchestrator",
            task_description=plan.primary_intent,
            entity_hints=plan.entity_hints
        )

        # Execute agents according to plan
        if plan.execution_mode == "parallel":
            # Run agents concurrently
            tasks = [
                self.agents[agent_name].execute(
                    capability=call.capability,
                    params=call.params,
                    context=context
                )
                for agent_name, call in plan.agent_calls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        elif plan.execution_mode == "sequential":
            # Run agents in order, passing results forward
            for agent_name, call in plan.agent_calls:
                result = await self.agents[agent_name].execute(
                    capability=call.capability,
                    params={**call.params, "previous_results": results},
                    context=context
                )
                results.append(result)

                # If result requires indexing, do it now
                if result.entities_to_index:
                    await self.indexer_agent.index_batch(result.entities_to_index)

        return results

    async def _format_response(
        self,
        results: list[AgentResult],
        plan: ExecutionPlan
    ) -> OrchestratorResponse:
        """
        Combine agent results into user-facing response.
        """
        # Check for any pending approvals
        pending = [r for r in results if r.requires_approval]
        if pending:
            self.pending_approvals.extend([
                PendingApproval(result=r, context=plan)
                for r in pending
            ])

        # Use Claude to synthesize response
        synthesis_prompt = f"""
        Synthesize these agent results into a helpful response for Dave.

        User's original request: {plan.primary_intent}

        Agent results:
        {self._format_results_for_synthesis(results)}

        Pending approvals needed: {len(pending)}

        Guidelines:
        - Be concise and direct
        - If approval needed, clearly state what and why
        - Offer follow-up suggestions if appropriate
        """

        response_text = await self._call_claude(synthesis_prompt)

        return OrchestratorResponse(
            text=response_text,
            agent_results=results,
            pending_approvals=pending,
            suggested_followups=self._generate_followup_suggestions(results)
        )
```

---

## Intent Recognition Examples

| User Says | Primary Intent | Agents Involved |
|-----------|---------------|-----------------|
| "What's on my calendar today?" | View schedule | Calendar |
| "Draft a reply to Laura's email" | Write response | Search → Email → Draft |
| "What follow-ups are overdue?" | Check commitments | Follow-Up |
| "What's on my todo list?" | View action items | TodoList |
| "What do I need to do this week?" | View upcoming tasks | TodoList + Follow-Up + Calendar |
| "This email is confusing" | Clarify request | Clarifier → Draft |
| "I don't understand what they want" | Clarify request | Search → Clarifier → Draft |
| "Prepare me for my 2pm meeting" | Meeting prep | Search → Meeting → Calendar |
| "Give me my morning briefing" | Daily summary | Briefing (calls TodoList + Clarifier) |
| "What's Park Place occupancy?" | Property metrics | Property |
| "Why hasn't Yanet responded?" | Investigate | Search → Follow-Up → Email |
| "Help me write an investor update" | Complex draft | Search → Property → Draft |

---

## Multi-Agent Workflows

Some requests require coordinated multi-agent execution:

**Example: "Prepare for my call with Steve Hinkle about the ROW dedication"**

```
1. Orchestrator analyzes: Meeting prep + specific topic

2. Search Agent gathers:
   - Steve Hinkle's contact profile
   - All emails mentioning "ROW" or "right of way"
   - Previous meetings with Steve
   - Open follow-ups with Steve
   - Park Place property context

3. Meeting Agent prepares:
   - Attendee context for Steve
   - Topic-specific history
   - Suggested discussion points

4. Follow-Up Agent checks:
   - Any pending items with Steve re: ROW
   - Last follow-up status

5. Orchestrator synthesizes:
   - Unified meeting prep document
   - Highlighted action items
   - Suggested questions to ask
```

---

*Continue to [04-data-flow.md](04-data-flow.md) for detailed data flow examples.*
