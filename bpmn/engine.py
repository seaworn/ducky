import pathlib
import re
from typing import Any, Self, TypedDict

from loguru import logger
from SpiffWorkflow.bpmn.parser import BpmnParser
from SpiffWorkflow.bpmn.serializer import BpmnWorkflowSerializer
from SpiffWorkflow.bpmn.workflow import BpmnWorkflow, Task
from SpiffWorkflow.camunda.parser.CamundaParser import CamundaParser
from SpiffWorkflow.camunda.serializer.config import CAMUNDA_CONFIG
from SpiffWorkflow.camunda.specs.user_task import Form, FormField
from SpiffWorkflow.camunda.specs.user_task import UserTask as CamundaUserTask
from SpiffWorkflow.util.task import TaskState


class CamundaSerializer(BpmnWorkflowSerializer):
    def __init__(self) -> None:
        registry = BpmnWorkflowSerializer.configure(CAMUNDA_CONFIG)
        super().__init__(registry)


def create_bpmn_engine() -> BpmnEngine:
    """
    Helper function to create a BpmnEngine
    DI -> Keep creation of the parser and serializer outside `BpmnEngine.__init__()`
    """

    parser = CamundaParser()
    serializer = CamundaSerializer()
    engine = BpmnEngine(parser, serializer)
    return engine


class BpmnEngine:
    """
    High-level engine that manages bpmn workflows.
    """

    def __init__(
        self,
        parser: BpmnParser,
        serializer: BpmnWorkflowSerializer,
    ):
        self.parser = parser
        self.serializer = serializer

    def load_from_file(self, bpmn_file: pathlib.Path | str) -> None:
        self.parser.add_bpmn_file(bpmn_file)

    def load_from_string(self, bpmn_xml: str) -> None:
        self.parser.add_bpmn_str(bpmn_xml.encode())

    def start_workflow(
        self,
        bpmn: str,
        process_id: str,
        data: dict | None = None,
        *,
        load_from_file: bool = False,
    ) -> Workflow:
        """
        1. Load given bpmn definition
        2. Create a new workflow for given process_id
        3. Start the workflow

        Attributes:
            bpmn: The bpmn definition as an xml string or file path
            process_id: The id of the process to start
            data: Optional task data to pass to the workflow
            load_from_file: Whether `bpmn` is a file path or an xml string
        """
        if load_from_file:
            path = pathlib.Path(bpmn)
            assert path.exists(), f"File not found at this path: {path}"
            self.load_from_file(bpmn)
        else:
            self.load_from_string(bpmn)
        spec = self.parser.get_spec(process_id, True)
        wf_bpmn = BpmnWorkflow(spec)
        wf = Workflow(wf_bpmn)
        self._run_workflow(wf, data)
        return wf

    def resume_workflow(
        self,
        serialization: dict,
        data: dict | None = None,
        start_task_id: str | None = None,
    ) -> Workflow:
        """
        Resume a running workflow

        Attributes:
            serialization: The serialized workflow
            data: Optional task data to pass to the workflow
            start_task_id: Optional id of the task to start from, otherwise the first task
        """
        wf = Workflow.create_from_serialization(self.serializer, serialization)
        self._run_workflow(wf, data, start_task_id)
        return wf

    def serialize_workflow(self, workflow: Workflow) -> dict:
        return workflow.serialize(self.serializer)

    def _run_workflow(
        self,
        workflow: Workflow,
        data: dict | None = None,
        start_task_id: str | None = None,
    ) -> None:
        try:
            workflow.run(data, start_task_id)
        except UserTaskFormValidationError as e:
            logger.error(str(e))
            # TODO: do something with the validation errors
        except Exception as e:
            logger.error(str(e))
            raise e


class Workflow:
    """
    Wraps a bpmn workflow.
    """

    def __init__(self, workflow: BpmnWorkflow) -> None:
        self.bpmn_workflow = workflow

    @classmethod
    def create_from_serialization(
        cls,
        serializer: BpmnWorkflowSerializer,
        serialization: dict,
    ) -> Self:
        wf_bpmn = serializer.deserialize_json(serialization)
        return cls(wf_bpmn)  # pyright: ignore [reportArgumentType]

    def run(self, data: dict | None = None, start_task_id: str | None = None) -> None:
        """
        Run a workflow to the next state
        Calls `Task.run` on all ready tasks until we enter a waiting state.

        Arguments:
            data: a dictionary containing data for tasks, keys correspond to the task name
        """

        if self.is_completed():
            return
        if data is None:
            data = {}
        start_task = (
            self.bpmn_workflow.get_task_from_id(start_task_id)
            if start_task_id
            else None
        )
        self.run_engine_tasks(data, start_task)
        # while there's a ready user task, attempt to complete it
        while task := self.get_next_user_task(start_task):
            logger.debug(f"Attempting to complete user task `{task.task_spec.name}`")
            # task data is taken from the data dict using the task spec name as key
            task_data = data.get(task.task_spec.name)
            if isinstance(task.task_spec, CamundaUserTask):
                validator = CamundaFormValidator(task.task_spec.form)
                errors = validator.validate(task_data or {})
                if errors:
                    logger.debug(
                        f"Could not complete user task `{task.task_spec.name}` due to form validation errors: {errors}"
                    )
                    raise UserTaskFormValidationError(task.task_spec.name, errors)
            if task_data:
                task.set_data(**task_data)
            task.run()
            start_task = task  # start at the just completed task
            self.run_engine_tasks(data, start_task)

    def is_completed(self) -> bool:
        return self.bpmn_workflow.is_completed()

    def run_engine_tasks(self, data: dict, start_task: Task | None = None) -> None:
        # get non-user tasks (manual=False)
        engine_tasks = self.bpmn_workflow.get_tasks(
            start_task, state=TaskState.NOT_FINISHED_MASK, manual=False
        )
        # update task data
        for task in engine_tasks:
            if task_data := data.get(task.task_spec.name):
                task.set_data(**task_data)
        # refresh state of all waiting task e.g. to update timer events
        self.bpmn_workflow.refresh_waiting_tasks(
            self.before_refresh_task, self.after_refresh_task
        )
        # complete tasks
        self.bpmn_workflow.do_engine_steps(
            self.before_complete_task, self.after_complete_task
        )

    def before_refresh_task(self, task: Task) -> None:
        logger.debug(f"Refreshing task `{task.task_spec.name}`")

    def after_refresh_task(self, task: Task) -> None:
        logger.debug(f"Refreshed task `{task.task_spec.name}`")

    def before_complete_task(self, task: Task) -> None:
        logger.debug(f"Running task `{task.task_spec.name}` with data `{task.data}`")

    def after_complete_task(self, task: Task) -> None:
        logger.debug(
            f"Completed task `{task.task_spec.name}` with status `{TaskState.get_name(task.state)}`"
        )

    def get_next_task_id(self) -> str | None:
        task = self.bpmn_workflow.get_next_task(state=TaskState.NOT_FINISHED_MASK)
        return task.task_spec.name if task else None

    def get_next_user_task(self, start_task: Task | None = None) -> Task | None:
        return self.bpmn_workflow.get_next_task(
            start_task, state=TaskState.NOT_FINISHED_MASK, manual=True
        )

    def serialize(self, serializer: BpmnWorkflowSerializer) -> dict:
        return serializer.serialize_json(self.bpmn_workflow)  # pyright: ignore [reportReturnType]


class CamundaFormValidator:
    """
    Validates user task data against a Camunda form definition.
    """

    def __init__(self, form: Form):
        self.form = form

    def validate(self, data: dict[str, Any]) -> list[FieldError]:
        errors = []
        for field in self.form.fields:
            value = data.get(field.id, field.default_value)
            field_errors = self.validate_field(field, value)
            if field_errors:
                errors.append(dict(id=field.id, label=field.label, errors=field_errors))
        return errors

    def validate_field(self, field: FormField, value: Any) -> list[str]:
        errors = []
        constraints = {v.name for f in self.form.fields for v in f.validation}
        for name in constraints:
            # field.has_validation() doesn't work for constraints with blank config e.g required. Possibly a bug in SpiffWorkflow.
            # if name in field.has_validation(name):
            if name in (v.name for v in field.validation):
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
        if config in ("", "0", "false", "False", "FALSE"):
            return
        if bool(config) is not bool(value):
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
        if not re.match(config, str(value), re.IGNORECASE | re.DOTALL):
            return f"Value does not match pattern {config}"

    def _warn_skip_validation(
        self, field: str, constraint: str, config: str | None, reason: str | None = None
    ) -> None:
        logger.warning(
            f"Field validation constraint `{constraint}` with config `{config}` skipped on field `{field}`{': ' + reason if reason else ''}"
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
    Common base class for all workflow runtime errors.
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
