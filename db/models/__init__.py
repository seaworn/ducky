from sqlalchemy import Column, ForeignKey, String, Integer, Text, DateTime, func
from sqlalchemy.orm import relationship

from db import Base
from db.repos import has_repo


class TimestampMixin:
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now())


@has_repo()
class BpmnProcess(Base, TimestampMixin):
    """Model for a bpmn process"""

    __tablename__ = 'bpmn_process'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    xml_definition = Column(Text, nullable=False)
    instances = relationship('BpmnProcessInstance', back_populates='process')

    def __repr__(self):
        return f'<BpmnProcess id={self.id} name={self.name}>'


@has_repo()
class BpmnProcessInstance(Base, TimestampMixin):
    """Model for an instance of bpmn process"""

    __tablename__ = 'bpmn_process_instance'
    id = Column(Integer, primary_key=True)
    bpmn_process_id = Column(ForeignKey('bpmn_process.id'), nullable=False)
    state = Column(Text, nullable=False)
    current_task = Column(String(255), nullable=False)
    process = relationship('BpmnProcess', back_populates='instances')

    def __repr__(self):
        return f'<BpmnProcessInstance id={self.id} process={self.process.name}>'
