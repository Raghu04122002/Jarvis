"""Supervisor — the AI model that coordinates agents.

The supervisor doesn't do the work itself. It:
1. plans a task and picks which agent should do it, and
2. reviews the agent's output and decides whether the work is done,
   writing a follow-up instruction when it isn't.

Every method returns None when the AI is unavailable or its answer can't be
used, so the orchestrator can fall back to its deterministic behaviour.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from jarvis.services.ai_service import AIService, AIServiceError

logger = logging.getLogger(__name__)

AGENT_DESCRIPTIONS: dict[str, str] = {
    "claude_code": (
        "Coding agent working inside the project repository: writes and edits code, "
        "fixes bugs, refactors, runs tests and shell commands, uses git."
    ),
    "antigravity": (
        "Agent for browser and visual UI work: navigating web pages, clicking "
        "through UIs, screenshots, end-to-end checks in a browser."
    ),
}

# Only the tail of long agent output is sent for review — it holds the summary
# and the final test results, and it keeps token use (free-tier quota) low.
_MAX_OUTPUT_CHARS = 6000
_MAX_STEPS = 8

_PLAN_SYSTEM = """You are the supervisor of Jarvis, a personal AI orchestration system.
You do not do the work yourself; you plan it and delegate it to one agent.

Available agents:
{agents}

Reply with only a JSON object:
{{"title": "<short task title, max 80 chars>",
  "steps": ["<concrete step>", ...],
  "agent": "<one agent name from the list>",
  "reason": "<one sentence on why this agent>"}}
Use 3-6 short, concrete steps specific to the request."""

_REVIEW_SYSTEM = """You are the supervisor of Jarvis, a personal AI orchestration system.
An agent was given a task and has finished. Judge from its output whether the
task is actually done. Treat it as not done if the output shows failing tests,
errors, unfinished steps, questions back to the user, or only a plan and no work.
Don't demand extras the request didn't ask for.

Reply with only a JSON object:
{"done": true or false,
 "summary": "<1-2 sentences for the user: what was done, or what is missing>",
 "follow_up": "<if not done: exact instruction for the agent to finish; else empty>"}"""


@dataclass(frozen=True)
class SupervisorPlan:
    title: str
    steps: list[str]
    agent: str | None
    reason: str


@dataclass(frozen=True)
class Review:
    done: bool
    summary: str
    follow_up: str


class Supervisor:
    """Plans tasks, delegates them to agents, and verifies the results."""

    def __init__(
        self,
        ai_service: AIService,
        agents: list[str],
        model: str | None = None,
    ) -> None:
        self._ai = ai_service
        self._agents = [a for a in agents if a in AGENT_DESCRIPTIONS] or list(agents)
        self._model = model or None

    @property
    def available(self) -> bool:
        return self._ai.available

    async def plan(self, request: str, context: str = "") -> SupervisorPlan | None:
        """Plan the request and choose an agent. None means: use the fallback planner."""
        agents = "\n".join(
            f"- {name}: {AGENT_DESCRIPTIONS.get(name, 'general agent')}" for name in self._agents
        )
        message = f"Request:\n{request}"
        if context:
            message += f"\n\nContext:\n{context}"

        data = await self._ask(_PLAN_SYSTEM.format(agents=agents), message)
        if data is None:
            return None

        steps_raw = data.get("steps")
        steps = (
            [str(s).strip() for s in steps_raw if str(s).strip()][:_MAX_STEPS]
            if isinstance(steps_raw, list)
            else []
        )
        if not steps:
            logger.warning("Supervisor plan had no steps; using fallback planner")
            return None

        title = str(data.get("title") or "").strip() or request.strip()
        if len(title) > 100:
            title = title[:97] + "..."

        agent = str(data.get("agent") or "").strip()
        if agent not in self._agents:
            if agent:
                logger.warning("Supervisor chose unknown agent %r; router will decide", agent)
            agent_choice: str | None = None
        else:
            agent_choice = agent

        return SupervisorPlan(
            title=title,
            steps=steps,
            agent=agent_choice,
            reason=str(data.get("reason") or "").strip(),
        )

    async def review(
        self,
        request: str,
        agent_name: str,
        output: str,
        attempt: int = 1,
    ) -> Review | None:
        """Decide whether the agent finished the task. None means: review unavailable."""
        if len(output) > _MAX_OUTPUT_CHARS:
            output = "[...earlier output truncated...]\n" + output[-_MAX_OUTPUT_CHARS:]
        message = (
            f"Task given to agent {agent_name!r} (attempt {attempt}):\n{request}\n\n"
            f"Agent output:\n{output or '(no output)'}"
        )
        data = await self._ask(_REVIEW_SYSTEM, message)
        if data is None:
            return None

        done = _as_bool(data.get("done"))
        if done is None:
            logger.warning("Supervisor review had no usable 'done' field")
            return None
        summary = str(data.get("summary") or "").strip()
        follow_up = str(data.get("follow_up") or "").strip()
        if not done and not follow_up:
            follow_up = summary or "Finish the remaining work in the task."
        return Review(done=done, summary=summary, follow_up=follow_up)

    async def _ask(self, system: str, message: str) -> dict[str, object] | None:
        if not self._ai.available:
            return None
        try:
            text = await self._ai.complete(system, message, model=self._model, json_mode=True)
        except AIServiceError as e:
            logger.warning("Supervisor call failed: %s", e)
            return None
        data = parse_json_object(text)
        if data is None:
            logger.warning("Supervisor returned non-JSON output: %.200s", text)
        return data


def parse_json_object(text: str) -> dict[str, object] | None:
    """Extract the first JSON object from model output (tolerates ``` fences / prose)."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _as_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):
        return value.strip().lower() == "true"
    return None
