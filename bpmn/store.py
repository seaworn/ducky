from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        stmt = select(models.BpmnWorkflowSpec).where(
            (models.BpmnWorkflowSpec.id == sid) | (models.BpmnWorkflowSpec.name == sid)
        )
        res = await self.session.scalars(stmt)
        workflow_spec = res.one_or_none()
        if workflow_spec:
            subworkflow_specs = await workflow_spec.awaitable_attrs.subworkflow_specs
            subworkflow_specs = {s.name: s.spec for s in subworkflow_specs}
            return (workflow_spec.spec, subworkflow_specs)

    async def save_workflow_spec(self, spec: dict, sub_specs: dict) -> SID:
        async def _create_or_update(spec):
            stmt = select(models.BpmnWorkflowSpec).where(
                models.BpmnWorkflowSpec.name == spec["name"]
            )
            res = await self.session.scalars(stmt)
            workflow_spec = res.one_or_none()
            if workflow_spec:
                await self._update_workflow_spec(workflow_spec, spec)
                return workflow_spec
            return await self._create_workflow_spec(spec)

        workflow_spec = await _create_or_update(spec)
        subworkflow_specs = await workflow_spec.awaitable_attrs.subworkflow_specs
        for sub_spec in sub_specs.values():
            subworkflow_spec = await _create_or_update(sub_spec)
            subworkflow_specs.append(subworkflow_spec)
        return workflow_spec.id

    async def _create_workflow_spec(self, spec: dict) -> models.BpmnWorkflowSpec:
        workflow_spec = models.BpmnWorkflowSpec(
            typename=spec["typename"],
            name=spec["name"],
            description=spec["description"],
            file=spec["file"],
            spec=spec,
            version=spec["serializer_version"],
        )
        self.session.add(workflow_spec)
        for t_name, t_spec in spec["task_specs"].items():
            task_spec = models.BpmnTaskSpec(
                workflow_spec=workflow_spec,
                typename=t_spec["typename"],
                name=t_name,
                description=t_spec["bpmn_name"] or t_spec["description"],
                manual=t_spec["manual"],
                subworkflow_spec=t_spec.get("spec"),
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
        task_specs = await workflow_spec.awaitable_attrs.task_specs
        for t_name, t_spec in spec["task_specs"].items():
            try:
                task_spec = next(
                    task_spec for task_spec in task_specs if task_spec.name == t_name
                )
            except StopIteration:
                task_spec = models.BpmnTaskSpec(workflow_spec=workflow_spec)
            task_spec.typename = t_spec["typename"]
            task_spec.name = t_name
            task_spec.description = t_spec["bpmn_name"] or t_spec["description"]
            task_spec.manual = t_spec["manual"]
            task_spec.subworkflow_spec = t_spec.get("spec")
        for task_spec in task_specs:
            if task_spec.name not in spec["task_specs"].keys():
                await self.session.delete(task_spec)

    async def get_workflow(self, sid: SID) -> dict | None:
        workflow = await self.session.get(models.BpmnWorkflow, sid)
        if workflow:
            return workflow.s_state

    async def save_workflow(self, s_state: dict, sid: SID | None = None) -> SID:
        if sid:
            workflow = await self.session.get(models.BpmnWorkflow, sid)
            if workflow:
                await self._update_workflow(workflow, s_state)
                return sid
        workflow = await self._create_workflow(s_state)
        return workflow.id

    async def _create_workflow(self, s_state: dict) -> models.BpmnWorkflow:
        stmt = select(models.BpmnWorkflowSpec).where(
            models.BpmnWorkflowSpec.name == s_state["spec"]["name"]
        )
        res = await self.session.scalars(stmt)
        workflow_spec = res.one()
        workflow = models.BpmnWorkflow(
            s_state=s_state,
            workflow_spec=workflow_spec,
            typename=s_state["typename"],
            last_task=s_state["last_task"],
            completed=s_state["completed"],
            version=s_state["serializer_version"],
        )
        self.session.add(workflow)
        for task in s_state["tasks"].values():
            await self._create_task(workflow, task)
        await self.session.flush()
        return workflow

    async def _create_task(
        self, workflow: models.BpmnWorkflow, s_state: dict
    ) -> models.BpmnTask:
        stmt = select(models.BpmnTaskSpec).where(
            models.BpmnTaskSpec.name == s_state["task_spec"],
            models.BpmnTaskSpec.workflow_spec_id == workflow.workflow_spec_id,
        )
        res = await self.session.scalars(stmt)
        task_spec = res.one()
        uid = UUID(s_state["id"])
        lsc = datetime.fromtimestamp(s_state["last_state_change"])
        task = models.BpmnTask(
            typename=s_state["typename"],
            state=s_state["state"],
            uid=uid,
            workflow=workflow,
            task_spec=task_spec,
            last_state_change=lsc,
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
        for t_id, t_state in s_state["tasks"].items():
            stmt = select(models.BpmnTask).where(models.BpmnTask.uid == UUID(t_id))
            res = await self.session.scalars(stmt)
            task = res.one_or_none()
            if not task:
                await self._create_task(workflow, t_state)
                continue
            task.state = t_state["state"]
            lsc = datetime.fromtimestamp(t_state["last_state_change"])
            task.last_state_change = lsc
            for key, value in t_state["data"].items():
                stmt = select(models.BpmnTaskData).where(
                    models.BpmnTaskData.task_id == task.id,
                    models.BpmnTaskData.key == key,
                )
                res = await self.session.scalars(stmt)
                task_data = res.one_or_none()
                if not task_data:
                    task_data = models.BpmnTaskData(key=key, value=value, task=task)
                    self.session.add(task_data)
                else:
                    task_data.value = value
