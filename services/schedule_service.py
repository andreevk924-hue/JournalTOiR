# services/schedule_service.py

from datetime import date, datetime, timedelta

from database.repository import Repository


class ScheduleService:
    def __init__(self, repository=None):
        self.repository = repository or Repository()

    def get_period(
        self,
        date_from,
        date_to,
        repair_type=None,
    ):
        start = self._to_date_string(date_from)
        end = self._to_date_string(date_to)

        if start > end:
            start, end = end, start

        return self.repository.get_work_for_period(
            date_from=start,
            date_to=end,
            repair_type=repair_type,
        )

    def build_schedule(
        self,
        date_from,
        date_to,
        repair_type=None,
    ):
        start_date = self._to_date(date_from)
        end_date = self._to_date(date_to)

        if start_date > end_date:
            start_date, end_date = (
                end_date,
                start_date,
            )

        rows = self.repository.get_work_for_period(
            date_from=start_date.isoformat(),
            date_to=end_date.isoformat(),
            repair_type=repair_type,
        )

        schedule = []

        for row in rows:
            work_start = self._to_date(
                row["date_start"]
            )

            if row["date_end"]:
                work_end = self._to_date(
                    row["date_end"]
                )
            else:
                work_end = end_date

            visible_start = max(
                work_start,
                start_date,
            )

            visible_end = min(
                work_end,
                end_date,
            )

            if visible_start > visible_end:
                continue

            schedule.append(
                {
                    "id": row["id"],
                    "equipment_id": row[
                        "equipment_id"
                    ],
                    "request_number": (
                        row["request_number"] or ""
                    ),
                    "model": row["model"],
                    "serial_number": row[
                        "serial_number"
                    ],
                    "garage_number": row[
                        "garage_number"
                    ],
                    "repair_type": (
                        row["repair_type"] or ""
                    ),
                    "date_start": work_start,
                    "date_end": (
                        self._to_date(
                            row["date_end"]
                        )
                        if row["date_end"]
                        else None
                    ),
                    "visible_start": visible_start,
                    "visible_end": visible_end,
                    "in_progress": bool(
                        row["in_progress"]
                    ),
                    "machine_hours": (
                        row["machine_hours"] or 0
                    ),
                    "executors": (
                        row["executors"] or ""
                    ),
                    "description": (
                        row["description"] or ""
                    ),
                }
            )

        return schedule

    def build_daily_matrix(
        self,
        date_from,
        date_to,
        repair_type=None,
    ):
        start_date = self._to_date(date_from)
        end_date = self._to_date(date_to)

        if start_date > end_date:
            start_date, end_date = (
                end_date,
                start_date,
            )

        dates = self._date_range(
            start_date,
            end_date,
        )

        schedule = self.build_schedule(
            start_date,
            end_date,
            repair_type,
        )

        machines = {}

        for work in schedule:
            equipment_id = work["equipment_id"]

            if equipment_id not in machines:
                machines[equipment_id] = {
                    "equipment_id": equipment_id,
                    "model": work["model"],
                    "serial_number": work[
                        "serial_number"
                    ],
                    "garage_number": work[
                        "garage_number"
                    ],
                    "days": {
                        current_date: []
                        for current_date in dates
                    },
                }

            current_date = work[
                "visible_start"
            ]

            while (
                current_date
                <= work["visible_end"]
            ):
                machines[
                    equipment_id
                ]["days"][current_date].append(
                    {
                        "work_id": work["id"],
                        "request_number": work[
                            "request_number"
                        ],
                        "repair_type": work[
                            "repair_type"
                        ],
                        "description": work[
                            "description"
                        ],
                        "executors": work[
                            "executors"
                        ],
                        "in_progress": work[
                            "in_progress"
                        ],
                    }
                )

                current_date += timedelta(
                    days=1
                )

        result = list(
            machines.values()
        )

        result.sort(
            key=lambda item: (
                item["model"].lower(),
                self._garage_sort_key(
                    item["garage_number"]
                ),
            )
        )

        return {
            "date_from": start_date,
            "date_to": end_date,
            "dates": dates,
            "machines": result,
        }

    @staticmethod
    def _date_range(
        date_from,
        date_to,
    ):
        result = []

        current = date_from

        while current <= date_to:
            result.append(current)

            current += timedelta(days=1)

        return result

    @staticmethod
    def _to_date(value):
        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, date):
            return value

        if not value:
            raise ValueError(
                "Дата не указана."
            )

        return date.fromisoformat(
            str(value)
        )

    @classmethod
    def _to_date_string(
        cls,
        value,
    ):
        return cls._to_date(
            value
        ).isoformat()

    @staticmethod
    def _garage_sort_key(value):
        text = str(
            value or ""
        ).strip()

        try:
            return (
                0,
                int(text),
            )

        except ValueError:
            return (
                1,
                text.lower(),
            )
