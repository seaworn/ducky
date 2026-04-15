from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict


class _CommonMixin:
    id: int
    created_at: datetime
    updated_at: datetime


class BpmnWorkflowSpec(BaseModel, _CommonMixin):
    model_config = ConfigDict(from_attributes=True)

    typename: str
    name: str
    description: str | None
    file: str | None
    spec: dict
    version: str | None


class BpmnWorkflowSpecForm(BaseModel):
    name: str
    bpmn_files: Sequence[UploadFile]
    dmn_files: Sequence[UploadFile] | None = None


class BpmnWorkflow(BaseModel, _CommonMixin):
    model_config = ConfigDict(from_attributes=True)

    typename: str
    last_task: str | None
    completed: bool
    s_state: dict
    version: str | None
    workflow_spec_id: int


class BpmnTaskSpec(BaseModel, _CommonMixin):
    model_config = ConfigDict(from_attributes=True)

    typename: str
    name: str
    description: str | None
    workflow_spec_id: int
    manual: bool
    spec: str | None


class BpmnTask(BaseModel, _CommonMixin):
    model_config = ConfigDict(from_attributes=True)

    typename: str
    uid: UUID
    state: int
    last_state_change: datetime
    task_spec_id: int
    workflow_id: int


class BpmnTaskData(BaseModel, _CommonMixin):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Any
    task_id: int
