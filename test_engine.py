from bpmn.engine import create_bpmn_engine

if __name__ == "__main__":
    engine = create_bpmn_engine()
    with open("bpmn/ducky.bpmn", "r") as f:
        bpmn_xml = f.read()
    data = None
    data = {"Activity_07fx4xs": {"variety": "DeadDuck", "tolerant": True}}
    wf = engine.start_workflow(bpmn_xml, "ducky", data)
    serialization = engine.serialize_workflow(wf)
    task_id = wf.get_next_task_id()
    print("Serialization:", serialization)
    print("Next task:", task_id)
