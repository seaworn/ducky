from tempfile import NamedTemporaryFile
from typing import Tuple, Optional

from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.camunda.parser.CamundaParser import CamundaParser
from SpiffWorkflow.camunda.specs.UserTask import UserTask
from SpiffWorkflow.bpmn.serializer.BpmnSerializer import BpmnSerializer
from loguru import logger

from db.models import BpmnProcess, BpmnProcessInstance


class StopWorkflow(Exception):
    """Signal to stop workflow execution"""


class BpmnRunner(object):
    """Manager for the creation and execution of a bpmn workflow"""

    def __init__(self, repo_manager):
        self.serializer = BpmnSerializer()
        self.repo_manager = repo_manager

    async def create_process_instance(self, process: BpmnProcess, data: Optional[dict] = None) -> BpmnProcessInstance:
        """Create a new process instance"""

        parser = CamundaParser()
        with NamedTemporaryFile(mode='w+t') as f:
            f.write(process.xml_definition)
            f.seek(0)
            parser.add_bpmn_file(f.name)
        wf_spec = parser.get_spec(process.name)
        workflow = BpmnWorkflow(wf_spec)
        state, next_task = self._run_to_next_state(workflow, data)
        repo = self.repo_manager.get_repo(BpmnProcessInstance)
        return await repo.create({'bpmn_process_id': process.id, 'state': state, 'current_task': next_task})

    async def run(self, process_instance: BpmnProcessInstance, data: Optional[dict] = None) -> BpmnProcessInstance:
        """Run workflow to the next ready state"""

        workflow = self.serializer.deserialize_workflow(process_instance.state)
        if workflow.is_completed():
            return process_instance
        state, next_task = self._run_to_next_state(workflow, data)
        repo = self.repo_manager.get_repo(BpmnProcessInstance)
        return await repo.update(process_instance.id, {'state': state, 'current_task': next_task})

    def _run_to_next_state(self, workflow: BpmnWorkflow, data: Optional[dict] = None) -> Tuple[str, str]:
        if data is None:
            data = {}
        workflow.do_engine_steps()
        ready_tasks = workflow.get_ready_user_tasks()
        try:
            # while there's a ready user task, attempt to complete it
            while len(ready_tasks) > 0:
                for task in ready_tasks:
                    if isinstance(task.task_spec, UserTask):
                        # task.update_data(data)
                        for field in task.task_spec.form.fields:
                            value = data.get(field.id)
                            if value is None:
                                logger.info(
                                    f"Task parameter '{field.id}' is not defined. Stopping workflow...")
                                raise StopWorkflow()
                            task.update_data_var(field.id, value)
                        workflow.complete_task_from_id(task.id)
                        logger.info(
                            f'Completed Task: ({task.get_name()}) {task.get_description()}')
                    # run intermediate engine tasks
                    workflow.do_engine_steps()
                    # update remaining user tasks
                    ready_tasks = workflow.get_ready_user_tasks()
        except StopWorkflow:
            pass
        # serialize the current state of the workflow
        state = self.serializer.serialize_workflow(workflow, include_spec=True)
        next_task = self._get_next_task(workflow)
        task_name = next_task.get_description() if next_task else 'END'
        return state, task_name

    def _get_next_task(self, workflow: BpmnWorkflow):
        """Get the next ready task"""

        if workflow.is_completed():
            return None
        return workflow.get_ready_user_tasks()[0]
