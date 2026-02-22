# Workflow orchestration: trigger interface and implementations.

from app.workflows.interface import WorkflowTrigger
from app.workflows.dummy_workflow import DummyWorkflowTrigger

__all__ = [
    "WorkflowTrigger",
    "DummyWorkflowTrigger",
]
