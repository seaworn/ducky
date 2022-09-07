from fastapi import Depends

from bpmn.bpmn_runner import BpmnRunner
from db.repos import RepoManager, get_repo_manager


def get_bpmn_runner(repo_manager: RepoManager = Depends(get_repo_manager)) -> BpmnRunner:
    return BpmnRunner(repo_manager)
