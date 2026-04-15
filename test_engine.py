import argparse
import asyncio
import json

from loguru import logger
from whistle import AsyncEventDispatcher

from bpmn.engine import create_bpmn_engine
from bpmn.store import SqlAlchemyDatabaseStore
from db import models
from db.database import Database

db = Database()

event_dispatcher = AsyncEventDispatcher()


async def _log_event(event):
    logger.debug(f"Received event: {event}")


event_dispatcher.add_listener("bpmn_engine.before_refresh_task", _log_event)
event_dispatcher.add_listener("bpmn_engine.after_refresh_task", _log_event)
event_dispatcher.add_listener("bpmn_engine.before_complete_task", _log_event)
event_dispatcher.add_listener("bpmn_engine.after_complete_task", _log_event)


async def _add(args):
    bpmn_files = [args.file]
    if args.bpmn_files:
        bpmn_files.extend(args.bpmn_files)
    async with db.session() as session, session.begin():
        store = SqlAlchemyDatabaseStore(session)
        engine = create_bpmn_engine(store, event_dispatcher)
        sid = await engine.add_workflow_spec(args.name, bpmn_files, args.dmn_files)
        logger.info(f"Added workflow spec: name={args.name}, sid={sid}")


async def _create(args):
    async with db.session() as session, session.begin():
        store = SqlAlchemyDatabaseStore(session)
        engine = create_bpmn_engine(store, event_dispatcher)
        sid = await engine.create_workflow(args.name, data=args.data, start=args.start)
        logger.info(f"Created workflow instance: name={args.name}, sid={sid}")


async def _run(args):
    async with db.session() as session, session.begin():
        store = SqlAlchemyDatabaseStore(session)
        engine = create_bpmn_engine(store, event_dispatcher)
        await engine.continue_workflow(args.id, data=args.data)
        workflow = await session.get_one(models.BpmnWorkflow, args.id)
        logger.info(
            f"Result: last_task={workflow.last_task}, completed={workflow.completed}"
        )


async def main():
    parser = argparse.ArgumentParser(
        prog="test-bpmn-engine", description="Test out the BPMN engine"
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    # add command
    add_cmd = subparsers.add_parser("add", help="Add a workflow spec")
    add_cmd.add_argument("name", help="Process ID")
    add_cmd.add_argument("file", help="Bpmn file")
    add_cmd.add_argument(
        "-b",
        "--bpmn-file",
        dest="bpmn_files",
        action="append",
        help="Additional bpmn file",
    )
    add_cmd.add_argument(
        "-d",
        "--dmn-file",
        dest="dmn_files",
        action="append",
        help="Additional dmn file",
    )
    add_cmd.set_defaults(func=_add)
    # create command
    create_cmd = subparsers.add_parser("create", help="Create a workflow instance")
    create_cmd.add_argument("name", help="Process ID")
    create_cmd.add_argument(
        "-D", "--data", type=json.loads, help="Task data to pass to the workflow"
    )
    create_cmd.add_argument(
        "-s", "--start", action="store_true", help="Start the workflow immediately"
    )
    create_cmd.set_defaults(func=_create)
    # run command
    run_cmd = subparsers.add_parser("run", help="Resume a running workflow")
    run_cmd.add_argument("id", help="Workflow ID")
    run_cmd.add_argument(
        "-D", "--data", type=json.loads, help="Task data to pass to the workflow"
    )
    run_cmd.set_defaults(func=_run)
    args = parser.parse_args()
    logger.debug(f"Command Args: {args}")
    await args.func(args)


if __name__ == "__main__":
    asyncio.run(main())
