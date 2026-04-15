from datetime import datetime
from typing import Self
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class _PKMixin:
    id: Mapped[int] = mapped_column(primary_key=True)


class _TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=sa.func.now())


class Base(DeclarativeBase, AsyncAttrs, _PKMixin, _TimestampMixin):
    pass


class BpmnWorkflowSpec(Base):
    """
    Database model for a bpmn workflow specification
    """

    __tablename__ = "bpmn_workflow_spec"

    typename: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(60), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(sa.String(255), nullable=True)
    file: Mapped[str] = mapped_column(sa.String(255), nullable=True)
    spec: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    version: Mapped[str] = mapped_column(sa.String(10), nullable=True)

    subworkflow_specs: Mapped[list[Self]] = relationship(
        "BpmnWorkflowSpec",
        secondary=sa.Table(
            "bpmn_workflow_spec_dependency",
            Base.metadata,
            sa.Column(
                "workflow_spec_id",
                sa.ForeignKey("bpmn_workflow_spec.id"),
                primary_key=True,
            ),
            sa.Column(
                "subworkflow_spec_id",
                sa.ForeignKey("bpmn_workflow_spec.id"),
                primary_key=True,
            ),
        ),
        primaryjoin="BpmnWorkflowSpec.id == bpmn_workflow_spec_dependency.c.workflow_spec_id",
        secondaryjoin="BpmnWorkflowSpec.id == bpmn_workflow_spec_dependency.c.subworkflow_spec_id",
    )
    task_specs: Mapped[list[BpmnTaskSpec]] = relationship(
        "BpmnTaskSpec", back_populates="workflow_spec"
    )
    workflows: Mapped[list[BpmnWorkflow]] = relationship(
        "BpmnWorkflow", back_populates="workflow_spec"
    )

    def __str__(self):
        return f"<{self.__name__} id={self.id} name={self.name}>"


class BpmnWorkflow(Base):
    """
    Database model for a running instance of a bpmn workflow spec
    """

    __tablename__ = "bpmn_workflow"

    typename: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    workflow_spec_id: Mapped[int] = mapped_column(
        sa.ForeignKey("bpmn_workflow_spec.id"), nullable=False
    )
    last_task: Mapped[str] = mapped_column(sa.String(255), nullable=True, unique=True)
    completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    s_state: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    version: Mapped[str] = mapped_column(sa.String(10), nullable=True)

    workflow_spec: Mapped[BpmnWorkflowSpec] = relationship(
        "BpmnWorkflowSpec", back_populates="workflows"
    )
    tasks: Mapped[list[BpmnTask]] = relationship("BpmnTask", back_populates="workflow")

    def __str__(self):
        return f"<{self.__name__} id={self.id} name={self.workflow_spec.name}>"


class BpmnTaskSpec(Base):
    """
    Database model for a bpmn task specification
    """

    __tablename__ = "bpmn_task_spec"
    __table_args__ = (sa.UniqueConstraint("workflow_spec_id", "name"),)

    typename: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    workflow_spec_id: Mapped[int] = mapped_column(
        sa.ForeignKey("bpmn_workflow_spec.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    description: Mapped[str] = mapped_column(sa.String(255), nullable=True)
    manual: Mapped[bool] = mapped_column(nullable=False, default=False)
    subworkflow_spec: Mapped[str] = mapped_column(sa.String(60), nullable=True)

    workflow_spec: Mapped[BpmnWorkflowSpec] = relationship(
        "BpmnWorkflowSpec", back_populates="task_specs"
    )
    tasks: Mapped[list[BpmnTask]] = relationship("BpmnTask", back_populates="task_spec")

    def __str__(self):
        return f"<{self.__name__} id={self.id} workflow_spec={self.workflow_spec.name} name={self.name}>"


class BpmnTask(Base):
    """
    Database model for a bpmn task
    """

    __tablename__ = "bpmn_task"
    # __table_args__ = (sa.UniqueConstraint("workflow_id", "task_spec_id"),)

    typename: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    uid: Mapped[UUID] = mapped_column(nullable=False, unique=True)
    workflow_id: Mapped[int] = mapped_column(
        sa.ForeignKey("bpmn_workflow.id"), nullable=False
    )
    task_spec_id: Mapped[int] = mapped_column(
        sa.ForeignKey("bpmn_task_spec.id"), nullable=False
    )
    state: Mapped[int] = mapped_column(nullable=False)
    last_state_change: Mapped[datetime] = mapped_column(nullable=False)

    workflow: Mapped[BpmnWorkflow] = relationship(
        "BpmnWorkflow", back_populates="tasks"
    )
    task_spec: Mapped[BpmnTaskSpec] = relationship(
        "BpmnTaskSpec", back_populates="tasks"
    )
    task_data: Mapped[list[BpmnTaskData]] = relationship(
        "BpmnTaskData", back_populates="task"
    )

    def __str__(self):
        return f"<{self.__name__} id={self.id} task_spec={self.task_spec.name}>"


class BpmnTaskData(Base):
    """
    Database model for a bpmn task data
    """

    __tablename__ = "bpmn_task_data"
    __table_args__ = (sa.UniqueConstraint("task_id", "key"),)

    task_id: Mapped[int] = mapped_column(sa.ForeignKey("bpmn_task.id"), nullable=False)
    key: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    value: Mapped[dict] = mapped_column(sa.JSON, nullable=False)

    task: Mapped[BpmnTask] = relationship("BpmnTask", back_populates="task_data")

    def __str__(self):
        return f"<{self.__name__} id={self.id} task_id={self.task_id} task_spec={self.task.task_spec.name}>"
