from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, load_only, selectinload

from db import models

type SID = int | str  # type for the identifier an object in the store


class AsyncStore(ABC):
    """
    A store provides the persistence layer for the workflow engine.
    This is the base class that defines the interface for an async workflow engine store.
    """

    @abstractmethod
    async def get_workflow_spec(self, sid: SID | str) -> tuple[dict, dict] | None:
        raise NotImplementedError()

    @abstractmethod
    async def save_workflow_spec(self, spec: dict, sub_specs: dict) -> SID:
        raise NotImplementedError()

    @abstractmethod
    async def get_workflow(self, sid: SID) -> dict | None:
        raise NotImplementedError()

    @abstractmethod
    async def save_workflow(self, s_state: dict, sid: SID | None = None) -> SID:
        raise NotImplementedError()


class SqlAlchemyDatabaseStore(AsyncStore):
    """
    A SQLAlchemy-based implementation of the AsyncStore interface.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_workflow_spec(self, sid: SID | str) -> tuple[dict, dict] | None:
        stmt = (
            select(ws := models.BpmnWorkflowSpec)
            .where((ws.id == sid) | (ws.name == sid))
            .options(
                selectinload(ws.subworkflow_specs).load_only(ws.name, ws.spec),
                load_only(ws.spec),
            )
        )
        res = await self.session.scalars(stmt)
        workflow_spec = res.one_or_none()
        if workflow_spec:
            subworkflow_specs = {
                s.name: s.spec for s in workflow_spec.subworkflow_specs
            }
            return (workflow_spec.spec, subworkflow_specs)

    async def save_workflow_spec(self, spec: dict, sub_specs: dict) -> SID:
        async def _create_or_update(spec):
            stmt = (
                select(ws := models.BpmnWorkflowSpec)
                .where(ws.name == spec["name"])
                .options(
                    selectinload(ws.subworkflow_specs).load_only(ws.name),
                    selectinload(ws.task_specs).load_only(models.BpmnTaskSpec.name),
                    load_only(ws.name),
                )
            )
            res = await self.session.scalars(stmt)
            workflow_spec = res.one_or_none()
            if workflow_spec:
                await self._update_workflow_spec(workflow_spec, spec)
                return workflow_spec
            return await self._create_workflow_spec(spec)

        workflow_spec = await _create_or_update(spec)
        for sub_spec in sub_specs.values():
            subworkflow_spec = await _create_or_update(sub_spec)
            workflow_spec.subworkflow_specs.append(subworkflow_spec)
        return workflow_spec.id

    async def _create_workflow_spec(self, spec: dict) -> models.BpmnWorkflowSpec:
        workflow_spec = models.BpmnWorkflowSpec(
            typename=spec["typename"],
            name=spec["name"],
            description=spec["description"],
            file=spec["file"],
            spec=spec,
            version=spec["serializer_version"],
            subworkflow_specs=[],  # avoid loading this relationship during append() which causes in MissingGreenlet error
        )
        self.session.add(workflow_spec)
        for t_name, t_spec in spec["task_specs"].items():
            task_spec = models.BpmnTaskSpec(
                typename=t_spec["typename"],
                name=t_name,
                description=t_spec["bpmn_name"] or t_spec["description"],
                manual=t_spec["manual"],
                spec=t_spec.get("spec"),
                workflow_spec=workflow_spec,
            )
            self.session.add(task_spec)
        await self.session.flush()
        return workflow_spec

    async def _update_workflow_spec(
        self, workflow_spec: models.BpmnWorkflowSpec, spec: dict
    ) -> None:
        workflow_spec.spec = spec
        workflow_spec.typename = spec["typename"]
        workflow_spec.name = spec["name"]
        workflow_spec.description = spec["description"]
        workflow_spec.file = spec["file"]
        for tspec in spec["task_specs"].values():
            task_spec = next(
                (s for s in workflow_spec.task_specs if s.name == tspec["name"]), None
            )
            if not task_spec:
                task_spec = models.BpmnTaskSpec(workflow_spec=workflow_spec)
                self.session.add(task_spec)
            task_spec.typename = tspec["typename"]
            task_spec.name = tspec["name"]
            task_spec.description = tspec["bpmn_name"] or tspec["description"]
            task_spec.manual = tspec["manual"]
            task_spec.spec = tspec.get("spec")
        for task_spec in workflow_spec.task_specs:
            if task_spec.name not in spec["task_specs"].keys():
                await self.session.delete(task_spec)

    async def get_workflow(self, sid: SID) -> dict | None:
        workflow = await self.session.get(
            w := models.BpmnWorkflow, sid, options=(load_only(w.s_state),)
        )
        if workflow:
            return workflow.s_state

    async def save_workflow(self, s_state: dict, sid: SID | None = None) -> SID:
        if sid:
            workflow = await self.session.get(
                w := models.BpmnWorkflow,
                sid,
                options=(
                    selectinload(w.tasks)
                    .load_only((t := models.BpmnTask).uid)
                    .selectinload(t.task_data)
                    .load_only(models.BpmnTaskData.key),
                    joinedload(w.workflow_spec)
                    .load_only((ws := models.BpmnWorkflowSpec).name)
                    .selectinload(ws.task_specs)
                    .load_only(models.BpmnTaskSpec.name),
                    load_only(w.id),
                ),
            )
            if workflow:
                await self._update_workflow(workflow, s_state)
                return sid
        workflow = await self._create_workflow(s_state)
        return workflow.id

    async def _create_workflow(self, s_state: dict) -> models.BpmnWorkflow:
        stmt = (
            select(ws := models.BpmnWorkflowSpec)
            .where(ws.name == s_state["spec"]["name"])
            .options(
                selectinload(ws.task_specs).load_only(models.BpmnTaskSpec.name),
                load_only(ws.name),
            )
        )
        res = await self.session.scalars(stmt)
        workflow_spec = res.one()
        workflow = models.BpmnWorkflow(
            s_state=s_state,
            typename=s_state["typename"],
            last_task=s_state["last_task"],
            completed=s_state["completed"],
            version=s_state["serializer_version"],
            workflow_spec=workflow_spec,
        )
        self.session.add(workflow)
        for tstate in s_state["tasks"].values():
            task_spec = next(
                s for s in workflow_spec.task_specs if s.name == tstate["task_spec"]
            )
            await self._create_task(workflow, task_spec, tstate)
        await self.session.flush()
        return workflow

    async def _create_task(
        self,
        workflow: models.BpmnWorkflow,
        task_spec: models.BpmnTaskSpec,
        s_state: dict,
    ) -> models.BpmnTask:
        task = models.BpmnTask(
            uid=UUID(s_state["id"]),
            typename=s_state["typename"],
            state=s_state["state"],
            last_state_change=datetime.fromtimestamp(s_state["last_state_change"]),
            workflow=workflow,
            task_spec=task_spec,
        )
        self.session.add(task)
        for key, value in s_state["data"].items():
            task_data = models.BpmnTaskData(key=key, value=value, task=task)
            self.session.add(task_data)
        return task

    async def _update_workflow(
        self, workflow: models.BpmnWorkflow, s_state: dict
    ) -> None:
        workflow.s_state = s_state
        workflow.last_task = s_state["last_task"]
        workflow.completed = s_state["completed"]
        for tstate in s_state["tasks"].values():
            task = next(
                (t for t in workflow.tasks if t.uid == UUID(tstate["id"])), None
            )
            if not task:
                task_spec = next(
                    s
                    for s in workflow.workflow_spec.task_specs
                    if s.name == tstate["task_spec"]
                )
                await self._create_task(workflow, task_spec, tstate)
                continue
            task.state = tstate["state"]
            task.last_state_change = datetime.fromtimestamp(tstate["last_state_change"])
            for key, value in tstate["data"].items():
                task_data = next((d for d in task.task_data if d.key == key), None)
                if not task_data:
                    task_data = models.BpmnTaskData(key=key, value=value, task=task)
                    self.session.add(task_data)
                else:
                    task_data.value = value
