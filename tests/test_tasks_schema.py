from datetime import date, datetime, timezone as dt_timezone

import pytest
from pydantic import ValidationError

from app.schemas.task import TaskCreate, TaskStatus


def _base_task_data():
    return {
        "topic": "Test Task",
        "tags": ["briefing"],
        "status": TaskStatus.SCHEDULED,
    }


def test_task_description_paragraph_limit():
    data = _base_task_data()
    data["description"] = "One.\n\nTwo.\n\nThree."
    with pytest.raises(ValidationError):
        TaskCreate(**data)


def test_task_completed_requires_timestamp():
    data = _base_task_data()
    data["status"] = TaskStatus.COMPLETED
    with pytest.raises(ValidationError):
        TaskCreate(**data)


def test_task_delayed_requires_until():
    data = _base_task_data()
    data["status"] = TaskStatus.DELAYED
    with pytest.raises(ValidationError):
        TaskCreate(**data)


def test_task_scheduled_end_before_start_rejected():
    data = _base_task_data()
    data["scheduled_start"] = datetime(2024, 1, 1, 10, tzinfo=dt_timezone.utc)
    data["scheduled_end"] = datetime(2024, 1, 1, 9, tzinfo=dt_timezone.utc)
    with pytest.raises(ValidationError):
        TaskCreate(**data)


def test_task_all_day_requires_date():
    data = _base_task_data()
    data["is_all_day"] = True
    with pytest.raises(ValidationError):
        TaskCreate(**data)


def test_task_scheduled_date_requires_all_day():
    data = _base_task_data()
    data["scheduled_date"] = date(2024, 1, 1)
    with pytest.raises(ValidationError):
        TaskCreate(**data)
