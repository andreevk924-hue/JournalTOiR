# database/models.py

from dataclasses import dataclass


@dataclass
class Equipment:
    id: int | None = None
    model: str = ""
    serial_number: str = ""
    garage_number: str = ""
    registration_number: str = ""
    manufacture_year: int | None = None
    current_hours: float = 0.0
    status: str = "В работе"
    note: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class WorkRecord:
    id: int | None = None
    equipment_id: int = 0
    request_number: str = ""
    repair_type: str = ""
    date_start: str = ""
    date_end: str | None = None
    in_progress: bool = True
    machine_hours: float = 0.0
    description: str = ""
    executors: str = ""
    requires_report: bool = False
    report_completed: bool = False
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Component:
    id: int | None = None
    equipment_id: int = 0
    component_name: str = ""
    serial_number: str = ""
    resource_hours: float = 0.0
    install_machine_hours: float = 0.0
    install_date: str = ""
    created_at: str = ""

    def worked_hours(
        self,
        machine_current_hours: float,
    ) -> float:
        return max(
            0.0,
            float(machine_current_hours or 0)
            - float(self.install_machine_hours or 0),
        )

    def remaining_hours(
        self,
        machine_current_hours: float,
    ) -> float:
        return (
            float(self.resource_hours or 0)
            - self.worked_hours(
                machine_current_hours
            )
        )

    def resource_percent(
        self,
        machine_current_hours: float,
    ) -> float:
        resource = float(
            self.resource_hours or 0
        )

        if resource <= 0:
            return 0.0

        return (
            self.remaining_hours(
                machine_current_hours
            )
            / resource
            * 100
        )


@dataclass
class Settings:
    organization_name: str = ""
    customer_name: str = ""
    logo_path: str = ""
    backup_path: str = ""
    backup_count: int = 30
