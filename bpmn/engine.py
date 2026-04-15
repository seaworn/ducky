import asyncio
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict, cast, override

from loguru import logger
from SpiffWorkflow.bpmn.parser import BpmnValidator
from SpiffWorkflow.bpmn.serializer import BpmnWorkflowSerializer
from SpiffWorkflow.bpmn.specs import BpmnProcessSpec
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow, Task
from SpiffWorkflow.camunda.parser.CamundaParser import CamundaParser
from SpiffWorkflow.camunda.serializer.config import CAMUNDA_CONFIG
from SpiffWorkflow.camunda.specs.user_task import Form as CamundaForm
from SpiffWorkflow.camunda.specs.user_task import FormField as CamundaFormField
from SpiffWorkflow.camunda.specs.user_task import UserTask as CamundaUserTask
from SpiffWorkflow.dmn.parser import BpmnDmnParser
from SpiffWorkflow.util.task import TaskState
from whistle import Event, IAsyncEventDispatcher

from bpmn.store import SID, AsyncStore
from util import fqn


def create_bpmn_engine(
    store: AsyncStore, event_dispatcher: IAsyncEventDispatcher
) -> BpmnEngine:
    """
    Helper function to create a BpmnEngine
    DI -> Keep creation of the parser and serializer outside `BpmnEngine.__init__()`
    """
    validator = BpmnValidator()
    parser = CamundaParser(validator=validator)
    serializer = CamundaSerializer()
    engine = BpmnEngine(parser, serializer, store, event_dispatcher)
    return engine


class BpmnEngine:
    """
    High-level engine that manages bpmn workflows.
    """

    def __init__(
        self,
        parser: BpmnDmnParser,
        serializer: BpmnWorkflowSerializer,
        store: AsyncStore,
        event_dispatcher: IAsyncEventDispatcher,
    ):
        self.parser = parser
        self.serializer = serializer
        self.store = store
        self.event_dispatcher = event_dispatcher

    async def add_workflow_spec(
        self,
        name: str,
        bpmn_files: Sequence[Path | str],
        dmn_files: Sequence[Path | str] | None = None,
    ) -> SID:
        def get_filename(f):
            if isinstance(f, str):
                f = Path(f)
            return str(f.resolve())

        self.parser.add_bpmn_files(get_filename(f) for f in bpmn_files)
        if dmn_files:
            self.parser.add_dmn_files(get_filename(f) for f in dmn_files)
        spec = cast(BpmnProcessSpec, self.parser.get_spec(name))
        s_spec = cast(dict, self.serializer.to_dict(spec))
        sub_specs = self.parser.get_subprocess_specs(name)
        s_sub_specs = {}
        for n, sub_spec in sub_specs.items():
            s_sub_specs[n] = cast(dict, self.serializer.to_dict(sub_spec))
        sid = await self.store.save_workflow_spec(s_spec, s_sub_specs)
        return sid

    async def create_workflow(
        self, spec_id: SID, data: dict | None = None, start: bool = True
    ) -> SID:
        """
        Create a workflow instance for given spec_id

        Arguments:
            spec_id: The store id or bpmn id of the process spec
            data: Optional task data to pass to the workflow
            start: Whether to start the workflow immediately, default is True
        """
        s_spec = await self.store.get_workflow_spec(spec_id)
        if s_spec is None:
            raise WorkflowRuntimeError(
                f"Workflow spec with name or id `{spec_id}` not found"
            )
        spec = cast(BpmnProcessSpec, self.serializer.from_dict(s_spec[0]))
        sub_specs = {}
        for n, s_sub_spec in s_spec[1].items():
            sub_specs[n] = cast(BpmnProcessSpec, self.serializer.from_dict(s_sub_spec))
        wf = BpmnWorkflow(spec, subprocess_specs=sub_specs)
        self._update_workflow_data(wf, data)
        if start:
            self._run_workflow(wf)
        s_state = cast(dict, self.serializer.to_dict(wf))
        sid = await self.store.save_workflow(s_state)
        return sid

    async def continue_workflow(
        self, workflow_id: SID, data: dict | None = None
    ) -> None:
        """
        Continue a running workflow

        Arguments:
            workflow_id: Store id of the workflow instance
            data: Optional task data to pass to the workflow
        """
        s_state = await self.store.get_workflow(workflow_id)
        if s_state is None:
            raise WorkflowRuntimeError(f"Workflow with id `{workflow_id}` not found")
        wf = cast(BpmnWorkflow, self.serializer.from_dict(s_state))
        self._update_workflow_data(wf, data)
        self._run_workflow(wf)
        s_state_new = cast(dict, self.serializer.to_dict(wf))
        await self.store.save_workflow(s_state_new, workflow_id)

    def _update_workflow_data(self, wf: BpmnWorkflow, data: dict | None = None) -> None:
        if not data:
            return
        for task in wf.get_tasks():
            task_data = data.get(task.task_spec.name)
            if task_data:
                task.set_data(**task_data)

    def _run_workflow(self, wf: BpmnWorkflow, start_task_id: str | None = None) -> None:
        """
        Run a bpmn workflow.
        Calls `Task.run()` on all ready tasks until we enter a waiting state.

        Arguments:
            start_task_id: the id of the task to start from, if None, starts from the beginning
        """

        if wf.is_completed():
            return

        async def before_refresh_task(task: Task) -> None:
            logger.debug(f"Refreshing task `{task.task_spec.name}`")
            await self.event_dispatcher.adispatch(
                "bpmn_engine.before_refresh_task", BpmnEngineEvent({"task_id": task.id})
            )

        async def after_refresh_task(task: Task) -> None:
            logger.debug(f"Refreshed task `{task.task_spec.name}`")
            await self.event_dispatcher.adispatch(
                "bpmn_engine.after_refresh_task", BpmnEngineEvent({"task_id": task.id})
            )

        async def before_complete_task(task: Task) -> None:
            logger.debug(
                f"Running task `{task.task_spec.name}` with data `{task.data}`"
            )
            await self.event_dispatcher.adispatch(
                "bpmn_engine.before_complete_task",
                BpmnEngineEvent({"task_id": task.id}),
            )

        async def after_complete_task(task: Task) -> None:
            logger.debug(
                f"Completed task `{task.task_spec.name}` with status `{TaskState.get_name(task.state)}`"
            )
            await self.event_dispatcher.adispatch(
                "bpmn_engine.after_complete_task", BpmnEngineEvent({"task_id": task.id})
            )

        def run_engine_tasks() -> None:
            def sync(cf):
                def f(*args, **kwargs):
                    asyncio.create_task(cf(*args, **kwargs))

                return f

            # refresh waiting task e.g. to update timer events
            wf.refresh_waiting_tasks(
                sync(before_refresh_task), sync(after_refresh_task)
            )
            # complete non-user tasks
            wf.do_engine_steps(sync(before_complete_task), sync(after_complete_task))

        def get_next_user_task(start_task: Task | None = None) -> Task | None:
            return wf.get_next_task(
                start_task, state=TaskState.NOT_FINISHED_MASK, manual=True
            )

        start_task = wf.get_task_from_id(start_task_id) if start_task_id else None
        run_engine_tasks()
        try:
            # while there's a ready user task, attempt to complete it
            while task := get_next_user_task(start_task):
                logger.debug(
                    f"Attempting to complete user task `{task.task_spec.name}`"
                )
                if isinstance(task.task_spec, CamundaUserTask):
                    validator = CamundaFormValidator(task.task_spec.form)
                    errors = validator.validate(task.data or {})
                    if errors:
                        logger.debug(
                            f"Could not complete user task `{task.task_spec.name}` due to form validation errors: {errors}"
                        )
                        raise UserTaskFormValidationError(task.task_spec.name, errors)
                task.run()
                start_task = (
                    task  # start from the just completed task in the next iteration
                )
                run_engine_tasks()
        except UserTaskFormValidationError as e:
            logger.warning(str(e))
        except Exception as e:
            logger.exception(str(e))


class BpmnEngineEvent(Event):
    """
    Base class for bpmn engine events.
    """

    def __init__(self, event_data: dict[str, Any]):
        super().__init__()
        self.data = event_data

    def __str__(self) -> str:
        return f"<{fqn(self)} data={self.data}>"


class CamundaSerializer(BpmnWorkflowSerializer):
    def __init__(self) -> None:
        registry = BpmnWorkflowSerializer.configure(CAMUNDA_CONFIG)
        super().__init__(registry)

    @override
    def to_dict(self, obj: Any, **kwargs) -> dict:
        dct: dict = super().to_dict(obj, **kwargs)  # pyright: ignore [reportAssignmentType]
        dct[self.VERSION_KEY] = self.VERSION
        return dct

    @override
    def from_dict(self, dct: dict, **kwargs) -> Any:
        self.migrate(dct)
        return super().from_dict(dct, **kwargs)


class CamundaFormValidator:
    """
    Validates user task data against a Camunda form definition.
    """

    def __init__(self, form: CamundaForm):
        self.form = form

    def validate(self, data: dict[str, Any]) -> list[FieldError]:
        errors = []
        for field in self.form.fields:
            value = data.get(field.id, field.default_value)
            field_errors = self.validate_field(field, value)
            if field_errors:
                errors.append(dict(id=field.id, label=field.label, errors=field_errors))
        return errors

    def validate_field(self, field: CamundaFormField, value: Any) -> list[str]:
        errors = []
        constraints = (v.name for v in field.validation)
        for name in constraints:
            config = field.get_validation(name)
            if config is None:
                config = ""
            validator = getattr(self, f"_validate_{name}", None)
            try:
                if not validator:
                    raise SkipValidation(
                        f"Validator for constraint `{name}` not defined"
                    )
                error = validator(config, value)
                if error:
                    errors.append(error)
                    if name == "required":
                        return errors  # early exit if required constraint fails
            except SkipValidation as e:
                self._warn_skip_validation(field.id, name, config, str(e))
        return errors

    def _validate_required(self, config: str, value: Any):
        # any of these is considered false so value is not required i.e. field is optional
        if config.lower() in ("0", "false", "no"):
            return
        if not value:
            return "Value is required"

    def _validate_length(self, config: str, value: Any) -> str | None:
        try:
            length = int(config)
            if len(value) < length:
                return f"Value must be {length} characters"
        except TypeError as e:
            raise SkipValidation() from e

    def _validate_minlength(self, config: str, value: Any) -> str | None:
        try:
            minlength = int(config)
            if len(value) < minlength:
                return f"Value must be at least {minlength} characters"
        except TypeError as e:
            raise SkipValidation() from e

    def _validate_maxlength(self, config: str, value: Any) -> str | None:
        try:
            maxlength = int(config)
            if len(value) > maxlength:
                return f"Value must be at most {maxlength} characters"
        except TypeError as e:
            raise SkipValidation() from e

    def _validate_min(self, config: str, value: Any) -> str | None:
        try:
            minvalue = float(config)
            if value < minvalue:
                return f"Value must be >= {minvalue}"
        except TypeError as e:
            raise SkipValidation() from e

    def _validate_max(self, config: str, value: Any) -> str | None:
        try:
            maxvalue = float(config)
            if value > maxvalue:
                return f"Value must be <= {maxvalue}"
        except TypeError as e:
            raise SkipValidation() from e

    def _validate_pattern(self, config: str, value: Any) -> str | None:
        config = config.strip()
        if not config:
            raise SkipValidation()
        if not re.match(config, str(value) if value else "", re.IGNORECASE | re.DOTALL):
            return f"Value does not match pattern {config}"

    def _warn_skip_validation(
        self, field: str, constraint: str, config: str, reason: str | None = None
    ) -> None:
        logger.warning(
            f"Field validation constraint `{constraint}` with config `{config}` skipped on field `{field}`"
            f"{': ' + reason if reason else ''}"
        )


class FieldError(TypedDict):
    id: str
    label: str | None
    errors: list[str]


class SkipValidation(Exception):
    """
    Signals a validation constraint for a field was skipped.
    """


class WorkflowRuntimeError(Exception):
    """
    Base class for engine runtime errors.
    """


class UserTaskFormValidationError(WorkflowRuntimeError):
    """
    Raised when a user task form validation fails.

    Attributes:
        task_spec_id (str): The ID of the user task spec.
        errors (list[FieldError]): A list of field validation errors.
    """

    def __init__(self, task_spec_id: str, errors: list[FieldError]) -> None:
        super().__init__(f"Form validation failed for user task '{task_spec_id}'")
        self.task_spec_id = task_spec_id
        self.errors = errors
