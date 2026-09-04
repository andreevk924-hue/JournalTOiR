# services/notification_service.py

from database.repository import Repository

from calendar import monthrange
from datetime import datetime, timedelta


class NotificationService:
    def __init__(
        self,
        repository=None,
        component_warning_percent=10,
    ):
        self.repository = repository or Repository()

        self.component_warning_percent = max(
            0,
            min(
                float(component_warning_percent),
                100,
            ),
        )

    def get_notifications(self):
        return self.repository.get_notifications(
            component_warning_percent=(
                self.component_warning_percent
            )
        )

    def get_missing_report_notifications(self):
        notifications = []

        rows = self.repository.get_missing_reports()

        for row in rows:
            notifications.append(
                {
                    "type": "missing_report",
                    "priority": "warning",
                    "work_id": row["id"],
                    "equipment_id": row["equipment_id"],
                    "title": "Требуется отчет",
                    "text": (
                        f"{row['model']} "
                        f"№{row['garage_number']}"
                    ),
                }
            )

        return notifications

    def get_component_notifications(self):
        notifications = []

        for row in (
            self.repository.get_components_over_resource()
        ):
            notifications.append(
                {
                    "type": "component_over_resource",
                    "priority": "critical",
                    "component_id": row["id"],
                    "equipment_id": row["equipment_id"],
                    "title": "Превышен ресурс компонента",
                    "text": (
                        f"{row['component_name']} — "
                        f"{row['model']} "
                        f"№{row['garage_number']}"
                    ),
                    "remaining_hours": row[
                        "remaining_hours"
                    ],
                }
            )

        for row in (
            self.repository.get_components_near_resource(
                self.component_warning_percent
            )
        ):
            notifications.append(
                {
                    "type": "component_near_resource",
                    "priority": "warning",
                    "component_id": row["id"],
                    "equipment_id": row["equipment_id"],
                    "title": "Заканчивается ресурс компонента",
                    "text": (
                        f"{row['component_name']} — "
                        f"{row['model']} "
                        f"№{row['garage_number']}"
                    ),
                    "remaining_hours": row[
                        "remaining_hours"
                    ],
                }
            )

        return notifications

    def get_notification_count(self):
        return len(
            self.get_notifications()
        )

    def has_notifications(self):
        return self.get_notification_count() > 0

    def get_critical_count(self):
        return sum(
            1
            for notification in self.get_notifications()
            if notification.get("priority")
            == "critical"
        )

    def get_warning_count(self):
        return sum(
            1
            for notification in self.get_notifications()
            if notification.get("priority")
            == "warning"
        )
    def _reactivate_due_recurring(self, now=None):
        now = now or datetime.now()
        self.repository.reactivate_due_recurring_reminders(
            now.isoformat(sep=" ", timespec="minutes")
        )

    def get_reminders(self, include_completed=True, limit=None):
        self._reactivate_due_recurring()
        return self.repository.get_reminders(include_completed=include_completed, limit=limit)

    def get_due_reminders(self, now=None):
        now = now or datetime.now()
        self._reactivate_due_recurring(now)
        result = []
        for row in self.repository.get_reminders(include_completed=False):
            try:
                due = datetime.fromisoformat(str(row["remind_at"]))
            except Exception:
                continue
            if due > now:
                continue
            last = row["last_notified_at"]
            if last:
                try:
                    if datetime.fromisoformat(str(last)) >= due:
                        continue
                except Exception:
                    pass
            result.append(row)
        return result

    def complete_reminder(self, reminder_id):
        row = self.repository.get_reminder(reminder_id)
        if row is None:
            return
        rule = str(row["repeat_rule"] or "once")
        if rule == "once":
            self.repository.set_reminder_completed(reminder_id, True)
            return
        try:
            current = datetime.fromisoformat(str(row["remind_at"]))
        except Exception:
            current = datetime.now()
        next_dt = self._next_occurrence(current, rule, datetime.now())
        # Повторяющаяся задача после отметки остаётся выполненной.
        # Она станет активной автоматически только когда наступит следующий срок.
        self.repository.reschedule_completed_reminder(
            reminder_id,
            next_dt.isoformat(sep=" ", timespec="minutes"),
        )

    @staticmethod
    def _next_occurrence(current, rule, now):
        candidate = current
        if rule == "daily":
            while candidate <= now:
                candidate += timedelta(days=1)
            return candidate
        if rule == "weekdays":
            while True:
                candidate += timedelta(days=1)
                if candidate.weekday() < 5 and candidate > now:
                    return candidate
        if rule == "weekly":
            while candidate <= now:
                candidate += timedelta(days=7)
            return candidate
        if rule == "monthly":
            original_day = current.day
            while candidate <= now:
                year = candidate.year + (1 if candidate.month == 12 else 0)
                month = 1 if candidate.month == 12 else candidate.month + 1
                day = min(original_day, monthrange(year, month)[1])
                candidate = candidate.replace(year=year, month=month, day=day)
            return candidate
        return now + timedelta(days=1)

