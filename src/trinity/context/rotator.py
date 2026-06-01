"""Session rotator — automatic context rotation when threshold is reached."""

from __future__ import annotations

import logging
import time

from trinity.agents.base import AgentWrapper
from trinity.context.shared import SharedContextEngine

logger = logging.getLogger(__name__)


class SessionRotator:
    """Handles session rotation for agents that hit context limits.

    Rotation flow:
    1. Ask the agent to summarize its work
    2. Write summary to shared.md session history
    3. Shut down the agent's current session
    4. Start a new session with summary + shared.md context injected
    5. Notify other agents

    The orchestrator calls rotate() when ContextMonitor flags an agent.
    """

    SUMMARY_PROMPT = """[System] 세션 교체를 위해 작업을 요약해주세요.

다음 정보를 간결하게 정리:
1. 완료한 작업
2. 진행 중인 작업 (현재 상태)
3. 다음에 해야 할 작업
4. 중요한 결정 사항과 그 이유

출력 형식:
## 완료
- ...
## 진행 중
- ...
## 다음 단계
- ...
## 결정 사항
- ..."""

    CONTINUATION_PROMPT = """[System] 이전 세션에서 이어서 작업합니다.

## 공유 컨텍스트
{shared_context}

## 이전 세션 요약
{session_summary}

## 당신의 역할
{agent_role}

위 컨텍스트를 숙지하고 작업을 계속 진행하세요."""

    def __init__(
        self,
        agents: dict[str, AgentWrapper],
        shared: SharedContextEngine,
        recent_rounds: int = 3,
    ):
        self.agents = agents
        self.shared = shared
        self.recent_rounds = recent_rounds
        self._rotation_count: dict[str, int] = {}

    async def rotate(self, agent_name: str) -> bool:
        """Perform session rotation for a specific agent.

        Returns True if rotation succeeded, False otherwise.
        """
        agent = self.agents.get(agent_name)
        if not agent:
            logger.error(f"Agent '{agent_name}' not found for rotation")
            return False

        logger.info(f"[{agent_name}] Starting session rotation...")
        start_time = time.time()

        try:
            # 1. Ask for summary
            logger.info(f"[{agent_name}] Requesting session summary...")
            summary_msg = await agent.send_and_wait(
                self.SUMMARY_PROMPT, timeout=60.0
            )
            summary = summary_msg.content

            # 2. Write summary to shared.md session history
            self.shared.append_session_summary(agent_name, summary)
            logger.info(f"[{agent_name}] Summary saved to shared.md")

            # 3. Shutdown current session
            await agent.graceful_shutdown()
            logger.info(f"[{agent_name}] Session shut down")

            # 4. Build continuation prompt and start new session
            shared_context = self.shared.get_context_for_rotation(
                recent_rounds=self.recent_rounds
            )
            role = agent.spec.role_prompt or agent_name

            continuation = self.CONTINUATION_PROMPT.format(
                shared_context=shared_context,
                session_summary=summary,
                agent_role=role,
            )

            await agent.start(initial_prompt=continuation)
            logger.info(f"[{agent_name}] New session started with context")

            # 5. Track rotation
            self._rotation_count[agent_name] = (
                self._rotation_count.get(agent_name, 0) + 1
            )

            elapsed = time.time() - start_time
            logger.info(
                f"[{agent_name}] Session rotation complete in {elapsed:.1f}s "
                f"(rotation #{self._rotation_count[agent_name]})"
            )

            return True

        except Exception as e:
            logger.error(f"[{agent_name}] Session rotation failed: {e}")
            # Try to restart the agent anyway
            try:
                await agent.start()
                logger.info(f"[{agent_name}] Agent restarted after failed rotation")
            except Exception as restart_error:
                logger.error(
                    f"[{agent_name}] Agent restart also failed: {restart_error}"
                )
            return False

    def get_rotation_count(self, agent_name: str) -> int:
        """Return how many times an agent has been rotated."""
        return self._rotation_count.get(agent_name, 0)

    def get_all_rotation_counts(self) -> dict[str, int]:
        """Return rotation counts for all agents."""
        return dict(self._rotation_count)

    def build_broadcast_message(self, agent_name: str) -> str:
        """Build a notification message for other agents about the rotation."""
        count = self._rotation_count.get(agent_name, 0)
        return (
            f"[{agent_name}의 세션이 교체되었습니다. "
            f"요약이 shared context에 반영되었습니다. "
            f"(교체 횟수: {count})]"
        )
