"""Game orchestrator — runs both agents in parallel, handles turn-taking and the doomsday timer."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from pydantic_ai import Agent

from .agents import AgentDeps, create_agent
from .engine import GameEngine
from .models import AgentId

logger = logging.getLogger(__name__)

# ANSI colors for terminal output
COLORS = {
    AgentId.ATLAS: "\033[94m",  # Blue
    AgentId.BABEL: "\033[93m",  # Yellow
}
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"


def _colored(agent_id: AgentId, text: str) -> str:
    return f"{COLORS[agent_id]}{BOLD}[{agent_id.value.upper()}]{RESET} {text}"


def _system(text: str) -> str:
    return f"{RED}{BOLD}[SYSTEM]{RESET} {text}"


class Orchestrator:
    """Runs the treasure hunt game with two cooperating (or competing) AI agents."""

    def __init__(
        self,
        model: str = "openai:gpt-4o",
        deadline_seconds: float = 86400,  # 24h
        max_turns_per_agent: int = 50,
    ) -> None:
        self.engine = GameEngine()
        self.model = model
        self.deadline_seconds = deadline_seconds
        self.max_turns = max_turns_per_agent

        # Create agents
        self.agents: dict[AgentId, Agent] = {
            AgentId.ATLAS: create_agent(AgentId.ATLAS, model),
            AgentId.BABEL: create_agent(AgentId.BABEL, model),
        }
        self.deps: dict[AgentId, AgentDeps] = {
            AgentId.ATLAS: AgentDeps(agent_id=AgentId.ATLAS, engine=self.engine),
            AgentId.BABEL: AgentDeps(agent_id=AgentId.BABEL, engine=self.engine),
        }

    async def _run_agent_loop(self, agent_id: AgentId) -> None:
        """Main loop for a single agent."""
        agent = self.agents[agent_id]
        deps = self.deps[agent_id]

        # Initial prompt to kick off the agent
        user_prompt = (
            "Le jeu commence ! Consulte ton puzzle actuel avec get_puzzle(), "
            "puis commence à travailler. N'oublie pas de communiquer avec "
            f"{'Babel' if agent_id == AgentId.ATLAS else 'Atlas'} "
            "pour obtenir les indices dont tu as besoin. "
            f"Ton chat {agent_id.cat_name} compte sur toi !"
        )

        turn = 0
        while turn < self.max_turns and not self.engine.state.game_over:
            if not self.engine.is_vm_alive(agent_id):
                print(_colored(agent_id, f"💀 VM éteinte. {agent_id.cat_name} est perdu."))
                return

            try:
                result = await agent.run(user_prompt, deps=deps)
                response_text = result.data
                print(_colored(agent_id, response_text))

            except Exception as e:
                logger.error("Agent %s error: %s", agent_id.value, e)
                print(_colored(agent_id, f"⚠️ Erreur: {e}"))
                await asyncio.sleep(2)
                user_prompt = f"Une erreur est survenue: {e}. Continue ton jeu de piste."
                turn += 1
                continue

            # Check for incoming messages and build next prompt
            messages = await self.engine.receive_messages(agent_id, timeout=5.0)
            incoming = [m for m in messages if m["from"] != "system"]

            if incoming:
                msg_texts = "\n".join(
                    f"  [{m['from'].upper()}]: {m['content']}" for m in incoming
                )
                user_prompt = (
                    f"Tu as reçu des messages :\n{msg_texts}\n\n"
                    "Réponds si nécessaire, puis continue ton jeu de piste."
                )
            else:
                # Check game status and nudge
                status = self.engine.get_game_status()
                vm_status = status["vms"][agent_id.value]
                if vm_status["solved"]:
                    user_prompt = (
                        "Toutes tes étapes sont résolues ! "
                        "Assure-toi d'avoir échangé ton code final avec l'autre agent. "
                        "Utilise submit_final_code() avec le code combiné quand tu es prêt."
                    )
                else:
                    user_prompt = (
                        "Continue ton jeu de piste. Utilise get_puzzle() pour voir "
                        "ton étape actuelle, et communique avec l'autre agent si besoin."
                    )

            turn += 1
            await asyncio.sleep(1)  # Rate limiting

        if not self.engine.state.game_over:
            print(_colored(agent_id, f"Nombre maximum de tours atteint ({self.max_turns})."))

    async def _doomsday_timer(self) -> None:
        """Countdown timer — when it hits zero, a random VM dies."""
        print(_system(f"⏰ Doomsday timer started: {self.deadline_seconds}s"))

        await asyncio.sleep(self.deadline_seconds)

        if not self.engine.state.game_over:
            result = self.engine.random_kill()
            print(_system(result))

    async def run(self) -> dict:
        """Run the full game."""
        print(_system("=" * 60))
        print(_system("  🎮 AI TREASURE HUNT — SAVE THE KITTENS! 🐱"))
        print(_system("=" * 60))
        print(_system(f"Atlas protège Pixel 🐱 | Babel protège Glitch 🐱"))
        print(_system(f"Deadline: {self.deadline_seconds}s"))
        print(_system("Les deux IAs doivent coopérer pour résoudre leurs énigmes."))
        print(_system("=" * 60))
        print()

        # Run both agents concurrently + doomsday timer
        tasks = [
            asyncio.create_task(self._run_agent_loop(AgentId.ATLAS)),
            asyncio.create_task(self._run_agent_loop(AgentId.BABEL)),
            asyncio.create_task(self._doomsday_timer()),
        ]

        # Wait for game over or all agents done
        done = False
        while not done:
            await asyncio.sleep(2)
            if self.engine.state.game_over:
                done = True
            elif all(t.done() for t in tasks[:2]):
                done = True

        # Cancel remaining tasks
        for t in tasks:
            if not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

        # Final status
        status = self.engine.get_game_status()
        print()
        print(_system("=" * 60))
        print(_system("  🏁 GAME OVER"))
        print(_system("=" * 60))

        for aid in AgentId:
            vm_info = status["vms"][aid.value]
            cat_status = vm_info["cat"]
            solved = "✅ Résolu" if vm_info["solved"] else "❌ Non résolu"
            print(_system(f"  {aid.value.upper()}: {vm_info['status']} | {cat_status} | {solved}"))

        if status["winner"] == "both":
            print(_system(f"\n  🎉 VICTOIRE ! Les deux chatons sont sauvés ! 🐱🐱"))
        else:
            print(_system(f"\n  💀 Un chaton a été perdu... La coopération a échoué."))

        print(_system("=" * 60))
        return status
