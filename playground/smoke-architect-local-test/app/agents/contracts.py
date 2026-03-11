from pydantic import BaseModel, Field


class PlanTask(BaseModel):
    id: str = Field(..., min_length=1)
    objective: str = Field(..., min_length=1)
    owner: str = Field(default="worker", min_length=1)


class PlanContract(BaseModel):
    goal: str = Field(..., min_length=1)
    strategy: str = Field(default="decompose_and_verify", min_length=1)
    tasks: list[PlanTask] = Field(default_factory=list)
    planner_output: str = Field(default="")


class WorkerResult(BaseModel):
    task_id: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)
    artifact: str = Field(default="")
    attempts: int = Field(default=1, ge=1)
    errors: list[str] = Field(default_factory=list)


class ReviewContract(BaseModel):
    approved: bool
    score: float = Field(ge=0.0, le=1.0)
    summary: str = Field(default="")
    issues: list[str] = Field(default_factory=list)
    final_answer: str = Field(default="")


class OrchestrationResult(BaseModel):
    plan: PlanContract
    workers: list[WorkerResult]
    review: ReviewContract
