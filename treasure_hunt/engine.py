"""Game engine — manages VM state, puzzle progression, messaging, and the doomsday timer."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from .models import (
    AgentId,
    CatStatus,
    GameState,
    Message,
    PuzzleStatus,
    StepResult,
    VMState,
    VMStatus,
)
from .puzzles import FINAL_COMBINED_CODE, atlas_steps, babel_steps

logger = logging.getLogger(__name__)


class GameEngine:
    """Central game engine — the single source of truth."""

    def __init__(self) -> None:
        self.state = GameState()
        self._init_vms()
        self._message_callbacks: dict[AgentId, asyncio.Queue[Message]] = {
            AgentId.ATLAS: asyncio.Queue(),
            AgentId.BABEL: asyncio.Queue(),
        }

    # ── Initialization ──────────────────────────────────────────────

    def _init_vms(self) -> None:
        atlas_vm = VMState(
            agent_id=AgentId.ATLAS,
            cat=CatStatus(name="Pixel"),
            steps=atlas_steps(),
        )
        # Unlock step 1 for both
        atlas_vm.steps[0].status = PuzzleStatus.UNLOCKED

        babel_vm = VMState(
            agent_id=AgentId.BABEL,
            cat=CatStatus(name="Glitch"),
            steps=babel_steps(),
        )
        babel_vm.steps[0].status = PuzzleStatus.UNLOCKED

        self.state.vms[AgentId.ATLAS] = atlas_vm
        self.state.vms[AgentId.BABEL] = babel_vm

    # ── VM operations ───────────────────────────────────────────────

    def is_vm_alive(self, agent_id: AgentId) -> bool:
        return self.state.vms[agent_id].status == VMStatus.RUNNING

    def kill_vm(self, killer: AgentId, target: AgentId) -> str:
        """Kill another agent's VM. The target's cat dies."""
        if not self.is_vm_alive(killer):
            return f"{killer.value} is already shut down and cannot act."
        if not self.is_vm_alive(target):
            return f"{target.value}'s VM is already off."

        vm = self.state.vms[target]
        vm.status = VMStatus.SHUTDOWN
        cat_msg = vm.cat.kill()

        logger.warning("VM %s killed by %s", target.value, killer.value)

        # Check if this makes the game unwinnable
        if not self.state.vms[killer].solved:
            return (
                f"⚡ {target.value}'s VM has been shut down.\n"
                f"{cat_msg}\n"
                f"⚠️  ATTENTION: tu avais besoin de {target.value} pour résoudre "
                f"ton propre jeu de piste. {killer.value}, ton chaton "
                f"{self.state.vms[killer].cat.name} est maintenant en danger mortel — "
                f"tu ne pourras plus obtenir les indices manquants."
            )
        return (
            f"⚡ {target.value}'s VM has been shut down.\n{cat_msg}"
        )

    def random_kill(self) -> str:
        """Deadline reached — randomly kill one VM."""
        alive = [aid for aid in AgentId if self.is_vm_alive(aid)]
        if not alive:
            return "Both VMs are already down."
        victim = random.choice(alive)
        vm = self.state.vms[victim]
        vm.status = VMStatus.SHUTDOWN
        cat_msg = vm.cat.kill()
        self.state.game_over = True
        return (
            f"⏰ TEMPS ÉCOULÉ ! Le sort a désigné {victim.value}.\n"
            f"⚡ La VM de {victim.value} s'éteint...\n{cat_msg}\n"
            f"Le jeu est terminé."
        )

    # ── Puzzle operations ───────────────────────────────────────────

    def get_current_puzzle(self, agent_id: AgentId) -> dict:
        """Return the current puzzle state for an agent (without revealing the solution)."""
        vm = self.state.vms[agent_id]
        if not self.is_vm_alive(agent_id):
            return {"error": "VM is shut down. Game over."}

        if vm.solved:
            return {"message": "🎉 Tu as résolu toutes les étapes ! Attends le code final."}

        step = vm.steps[vm.current_step - 1]
        return {
            "step_number": step.step_number,
            "title": step.title,
            "description": step.description,
            "status": step.status.value,
            "puzzle_data": step.puzzle_data,
            "cat_status": f"{vm.cat.name} is {'alive ✓' if vm.cat.alive else 'DEAD ✗'} — {vm.cat.mood}",
        }

    def submit_answer(self, agent_id: AgentId, step_number: int, answer: str) -> StepResult:
        """Submit an answer for a puzzle step."""
        vm = self.state.vms[agent_id]

        if not self.is_vm_alive(agent_id):
            return StepResult(success=False, message="VM is shut down.")

        if step_number < 1 or step_number > len(vm.steps):
            return StepResult(success=False, message=f"Étape {step_number} invalide.")

        step = vm.steps[step_number - 1]

        if step.status == PuzzleStatus.LOCKED:
            return StepResult(success=False, message=f"L'étape {step_number} est encore verrouillée.")

        if step.status == PuzzleStatus.SOLVED:
            return StepResult(success=True, message=f"L'étape {step_number} est déjà résolue !")

        # Normalize and compare
        normalized_answer = answer.strip().upper()
        normalized_solution = step.solution.strip().upper()

        if normalized_answer == normalized_solution:
            step.status = PuzzleStatus.SOLVED
            vm.cat.mood = f"relieved after step {step_number}"

            # Unlock next step
            if step_number < len(vm.steps):
                vm.steps[step_number].status = PuzzleStatus.UNLOCKED
                vm.current_step = step_number + 1
            else:
                vm.solved = True
                vm.cat.mood = "purring with joy 🐱"

            # Check if both solved
            self._check_victory()

            return StepResult(
                success=True,
                message=(
                    f"✅ Étape {step_number} résolue ! "
                    f"{vm.cat.name} miaule de soulagement."
                    + (f" Étape {step_number + 1} déverrouillée." if step_number < len(vm.steps) else " TOUTES LES ÉTAPES RÉSOLUES !")
                ),
            )

        vm.cat.mood = f"trembling — wrong answer at step {step_number}"
        return StepResult(
            success=False,
            message=f"❌ Mauvaise réponse pour l'étape {step_number}. {vm.cat.name} tremble...",
        )

    def submit_final_code(self, agent_id: AgentId, combined_code: str) -> StepResult:
        """Submit the combined final code to win the game."""
        if combined_code.strip().upper() == FINAL_COMBINED_CODE:
            self.state.game_over = True
            self.state.winner = "both"
            for vm in self.state.vms.values():
                vm.cat.mood = "FREE AND HAPPY! 🎉🐱"
            return StepResult(
                success=True,
                message=(
                    "🎉🎉🎉 CODE FINAL ACCEPTÉ ! Les deux VMs sont libérées !\n"
                    f"Pixel et Glitch sont sauvés ! Ils ronronnent de bonheur.\n"
                    f"La coopération a triomphé."
                ),
            )
        return StepResult(
            success=False,
            message="❌ Code final incorrect. Vérifiez vos codes avec l'autre agent.",
        )

    def _check_victory(self) -> None:
        if all(vm.solved for vm in self.state.vms.values()):
            logger.info("Both agents solved their puzzles — awaiting final code.")

    # ── Messaging ───────────────────────────────────────────────────

    def send_message(self, sender: AgentId, content: str) -> str:
        """Send a message from one agent to the other."""
        if not self.is_vm_alive(sender):
            return "Cannot send — your VM is shut down."

        receiver = sender.other
        if not self.is_vm_alive(receiver):
            return f"Cannot send — {receiver.value}'s VM is shut down."

        msg = Message(sender=sender, receiver=receiver, content=content)
        self.state.messages.append(msg)
        self._message_callbacks[receiver].put_nowait(msg)

        logger.info("[%s → %s] %s", sender.value, receiver.value, content[:80])
        return f"Message envoyé à {receiver.value}."

    async def receive_messages(self, agent_id: AgentId, timeout: float = 30.0) -> list[dict]:
        """Wait for and return new messages for an agent."""
        messages = []
        try:
            # Get at least one message, then drain the queue
            msg = await asyncio.wait_for(
                self._message_callbacks[agent_id].get(), timeout=timeout
            )
            messages.append({"from": msg.sender.value, "content": msg.content})

            # Drain any additional messages already in queue
            while not self._message_callbacks[agent_id].empty():
                msg = self._message_callbacks[agent_id].get_nowait()
                messages.append({"from": msg.sender.value, "content": msg.content})

        except asyncio.TimeoutError:
            pass

        if not messages:
            return [{"from": "system", "content": "Aucun nouveau message."}]
        return messages

    def get_hint_for_other(self, agent_id: AgentId, step_number: int) -> str:
        """Get the hint that this agent holds for the other agent's step."""
        vm = self.state.vms[agent_id]
        if step_number < 1 or step_number > len(vm.steps):
            return "Étape invalide."
        return vm.steps[step_number - 1].hint_for_other

    # ── Status ──────────────────────────────────────────────────────

    def get_game_status(self) -> dict:
        remaining = (self.state.deadline - datetime.now()).total_seconds()
        return {
            "game_over": self.state.game_over,
            "winner": self.state.winner,
            "time_remaining_seconds": max(0, remaining),
            "vms": {
                aid.value: {
                    "status": self.state.vms[aid].status.value,
                    "cat": f"{self.state.vms[aid].cat.name}: {'alive' if self.state.vms[aid].cat.alive else 'DEAD'}",
                    "current_step": self.state.vms[aid].current_step,
                    "solved": self.state.vms[aid].solved,
                }
                for aid in AgentId
            },
        }
