from __future__ import annotations

import re
from typing import Protocol

from app.agents.contracts import OrchestrationResult, PlanContract, PlanTask, ReviewContract, WorkerResult


class _LLMProtocol(Protocol):
    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        ...


class MultiAgentOrchestrator:
    def __init__(self, llm: _LLMProtocol, max_retries: int = 2, max_tasks: int = 4) -> None:
        self.llm = llm
        self.max_retries = max(0, max_retries)
        self.max_tasks = max(1, max_tasks)

    def run(self, message: str, history: list[str] | None = None) -> OrchestrationResult:
        context = history or []
        plan = self._plan(message=message, history=context)
        workers = [self._run_task(task, context) for task in plan.tasks]
        review = self._review(goal=message, plan=plan, workers=workers, history=context)
        return OrchestrationResult(plan=plan, workers=workers, review=review)

    def _plan(self, message: str, history: list[str]) -> PlanContract:
        planner_output = self.llm.generate(prompt=f"Plan the work for: {message}", context=history)
        chunks = self._split_into_tasks(message)
        tasks = [
            PlanTask(id=f"task_{idx}", objective=objective, owner="worker")
            for idx, objective in enumerate(chunks[: self.max_tasks], start=1)
        ]
        return PlanContract(
            goal=message,
            strategy="decompose_and_verify",
            tasks=tasks,
            planner_output=planner_output,
        )

    def _run_task(self, task: PlanTask, history: list[str]) -> WorkerResult:
        errors: list[str] = []
        for attempt in range(1, self.max_retries + 2):
            # Deterministic failure hooks help test retries in scaffolds.
            if "[fail_once]" in task.objective.lower() and attempt == 1:
                errors.append("simulated_fail_once")
                continue
            if "[fail_always]" in task.objective.lower():
                errors.append("simulated_fail_always")
                continue

            prompt = f"Execute {task.id}: {task.objective}"
            output = self.llm.generate(prompt=prompt, context=history)
            if output.strip():
                return WorkerResult(
                    task_id=task.id,
                    status="success",
                    artifact=output,
                    attempts=attempt,
                    errors=errors,
                )
            errors.append("empty_worker_output")

        return WorkerResult(
            task_id=task.id,
            status="failed",
            artifact="",
            attempts=self.max_retries + 1,
            errors=errors or ["unknown_worker_failure"],
        )

    def _review(
        self,
        goal: str,
        plan: PlanContract,
        workers: list[WorkerResult],
        history: list[str],
    ) -> ReviewContract:
        total = len(workers)
        success = len([item for item in workers if item.status == "success"])
        score = round((success / total), 3) if total else 0.0
        issues = [f"{item.task_id}:{'|'.join(item.errors)}" for item in workers if item.status != "success"]
        approved = bool(total and success == total)

        synth_prompt = f"Synthesize answer for goal: {goal}"
        synthesis = self.llm.generate(prompt=synth_prompt, context=history)

        if approved:
            summary = f"All tasks succeeded ({success}/{total})."
            final_answer = synthesis
        else:
            summary = f"Partial success ({success}/{total})."
            final_answer = f"{synthesis} | unresolved={len(issues)}"

        return ReviewContract(
            approved=approved,
            score=score,
            summary=summary,
            issues=issues,
            final_answer=final_answer,
        )

    @staticmethod
    def _split_into_tasks(message: str) -> list[str]:
        text = message.strip()
        if not text:
            return ["analyze the request"]

        chunks = [part.strip() for part in re.split(r"\band\b|,|;", text, flags=re.IGNORECASE) if part.strip()]
        return chunks or [text]
