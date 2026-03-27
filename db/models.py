from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from db.repository import Repository


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=func.now())


class BpmnProcess(Base):
    """
    Database model for a bpmn process
    """

    __tablename__ = "bpmn_process"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    xml_definition: Mapped[str] = mapped_column(Text, nullable=False)
    bpmn_process_instances: Mapped[list["BpmnProcessInstance"]] = relationship(
        "BpmnProcessInstance", back_populates="bpmn_process"
    )

    def __str__(self):
        return f"<{self.__name__} id={self.id} name={self.name}>"


class BpmnProcessRepository(Repository[BpmnProcess]):
    model = BpmnProcess

    async def find_by_name(self) -> None:
        pass


class BpmnProcessInstance(Base):
    """
    Database model for an instance of a bpmn process
    """

    __tablename__ = "bpmn_process_instance"

    bpmn_process_id: Mapped[int] = mapped_column(
        ForeignKey("bpmn_process.id"), nullable=False
    )
    bpmn_process: Mapped["BpmnProcess"] = relationship(
        "BpmnProcess", back_populates="bpmn_process_instances"
    )
    serialization: Mapped[dict] = mapped_column(JSON, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    completed: Mapped[bool] = mapped_column(nullable=False, default=False)

    def __str__(self):
        return f"<{self.__name__} id={self.id} bpmn_process={self.bpmn_process.name}, task_id={self.task_id}>"


class BpmnProcessInstanceRepository(Repository[BpmnProcessInstance]):
    model = BpmnProcessInstance
