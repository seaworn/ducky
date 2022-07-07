from SpiffWorkflow.bpmn.workflow import BpmnWorkflow
from SpiffWorkflow.camunda.parser.CamundaParser import CamundaParser
from SpiffWorkflow.camunda.specs.UserTask import UserTask, EnumFormField


def show_form(task):
    model = {}
    form = task.task_spec.form

    if task.data is None:
        task.data = {}

    for field in form.fields:
        prompt = field.label
        if isinstance(field, EnumFormField):
            prompt += '? (Options: %s): ' % ' | '.join([str(option.name) for option in field.options])
            answer = input(prompt)
        if field.type == "boolean":
            prompt += " (Options: yes, no): "
            answer = input(prompt)
        if field.type == "long":
            answer = int(answer)
        if field.type == "boolean":
            answer = answer.lower().strip()
            answer = (answer == 'true' or answer == 'yes')
        task.update_data_var(field.id, answer)


parser = CamundaParser()
parser.add_bpmn_file('ducky/ducky.bpmn')
spec = parser.get_spec('ducky')
workflow = BpmnWorkflow(spec)

workflow.do_engine_steps()
ready_tasks = workflow.get_ready_user_tasks()
while len(ready_tasks) > 0:
    for task in ready_tasks:
        if isinstance(task.task_spec, UserTask):
            show_form(task)
            workflow.complete_task_from_id(task.id)
        workflow.do_engine_steps()
        ready_tasks = workflow.get_ready_user_tasks()
