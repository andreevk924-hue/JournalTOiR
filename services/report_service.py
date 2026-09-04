# services/report_service.py
"""Единый расчётный слой для сводок и отчётов.

Главный принцип: отчёты считаются не только по шапке work_records, а по
фактическому состоянию техники КАЖДЫЙ день. Если для дня есть запись в
work_daily_log, именно она является источником истины. Это важно, потому что
внутри одной карточки ремонта день может быть аварийным ремонтом, следующим
днём простоем, затем снова ремонтом или работами заказчика.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from database.repository import Repository


class ReportService:
    UNAVAILABLE_STATES = {
        "Аварийный ремонт",
        "Плановый ремонт",
        "Модернизация",
        "Простой",
        "ТО",
    }

    def __init__(self, repository=None):
        self.repository = repository or Repository()

    # ------------------------------------------------------------------
    # Canonical timeline
    # ------------------------------------------------------------------

    def get_daily_timeline(self, date_from, date_to):
        """Возвращает фактическое состояние работ по дням.

        Одна строка = одна карточка работы в один календарный день.

        Правила:
        * work_daily_log перекрывает тип/описание/исполнителей шапки работы;
        * незавершённая работа не растягивается в будущее дальше текущего дня;
        * ещё не начатое запланированное ТО не считается фактической работой;
        * старый флаг is_planned у НЕ-ТО не скрывает реальные ремонты;
        * завершённая работа ограничивается date_end.
        """
        start, end = self._normalize_period(date_from, date_to)
        today = date.today()

        works = self.repository.get_work_for_period(
            date_from=start.isoformat(),
            date_to=end.isoformat(),
        )
        try:
            daily_rows = self.repository.get_work_daily_for_period(
                start.isoformat(), end.isoformat()
            )
        except Exception:
            # Старые БД без work_daily_log всё равно должны строить отчёты.
            daily_rows = []

        daily_map = {}
        for row in daily_rows:
            try:
                key = (self._value(row, "work_id"), self._to_date(self._value(row, "work_date")))
            except Exception:
                continue
            daily_map[key] = row

        facts = []
        for work in works:
            try:
                work_start = self._to_date(self._value(work, "date_start"))
            except Exception:
                continue

            repair_type = self.normalize_state(self._value(work, "repair_type"))
            is_planned = bool(self._value(work, "is_planned", 0))
            is_started = bool(self._value(work, "is_started", 0))
            in_progress = bool(self._value(work, "in_progress", 0))

            # Новый механизм планирования: только плановое ТО до команды
            # «Начать ТО» является планом, а не фактической работой.
            if repair_type == "ТО" and is_planned and not is_started:
                continue

            daily_authoritative_from = None
            raw_authoritative_from = str(
                self._value(work, "daily_log_authoritative_from", "") or ""
            ).strip()
            if raw_authoritative_from:
                try:
                    daily_authoritative_from = self._to_date(
                        raw_authoritative_from
                    )
                except Exception:
                    daily_authoritative_from = None

            raw_end = self._value(work, "date_end")
            if raw_end:
                try:
                    work_end = self._to_date(raw_end)
                except Exception:
                    work_end = work_start
            elif in_progress:
                # Нельзя считать будущие дни фактическим ремонтом/простоем.
                work_end = today
            else:
                work_end = work_start

            # Работа, начинающаяся в будущем, ещё не является фактом.
            if work_start > today and not raw_end:
                continue

            visible_start = max(start, work_start)
            visible_end = min(end, work_end, today)
            if visible_start > visible_end:
                continue

            current = visible_start
            while current <= visible_end:
                daily = daily_map.get((self._value(work, "id"), current))

                if (
                    daily is None
                    and daily_authoritative_from is not None
                    and current >= daily_authoritative_from
                ):
                    current += timedelta(days=1)
                    continue

                state = repair_type
                description = str(self._value(work, "description", "") or "").strip()
                executors = str(self._value(work, "executors", "") or "").strip()
                machine_hours = self._number(self._value(work, "machine_hours", 0))

                if daily is not None:
                    # Дневная запись — источник истины именно за этот день.
                    # Пустой исполнитель/описание тоже являются осознанным значением
                    # и не должны незаметно подменяться данными из шапки карточки.
                    state = self.normalize_state(self._value(daily, "day_type")) or state
                    description = str(self._value(daily, "description", "") or "").strip()
                    executors = str(self._value(daily, "executors", "") or "").strip()
                    machine_hours = self._number(self._value(daily, "machine_hours", 0))

                facts.append({
                    "date": current,
                    "work_id": self._value(work, "id"),
                    "equipment_id": self._value(work, "equipment_id"),
                    "model": self._value(work, "model", ""),
                    "serial_number": self._value(work, "serial_number", ""),
                    "garage_number": self._value(work, "garage_number", ""),
                    "request_number": self._value(work, "request_number", ""),
                    "state": state or "Не указано",
                    "description": description,
                    "executors": executors,
                    "machine_hours": machine_hours,
                    "in_progress": in_progress,
                    "is_planned": is_planned,
                    "is_started": is_started,
                    "has_daily_entry": daily is not None,
                })
                current += timedelta(days=1)

        facts.sort(key=lambda x: (x["date"], str(x["model"]).lower(), str(x["garage_number"]).lower(), x["work_id"]))
        return facts

    def get_timeline_matrix(self, date_from, date_to):
        """Удобная матрица для графика работ: (equipment_id, date) -> facts."""
        facts = self.get_daily_timeline(date_from, date_to)
        matrix = defaultdict(list)
        for fact in facts:
            matrix[(fact["equipment_id"], fact["date"])].append(fact)
        return matrix

    def get_state_segments(self, date_from, date_to, state):
        """Склеивает соседние дни одного состояния в понятные интервалы."""
        target = self.normalize_state(state)
        facts = [f for f in self.get_daily_timeline(date_from, date_to) if f["state"] == target]
        grouped = defaultdict(list)
        for fact in facts:
            grouped[fact["work_id"]].append(fact)

        result = []
        for work_id, items in grouped.items():
            items.sort(key=lambda x: x["date"])
            segment = []
            previous = None
            for item in items:
                if previous is None or item["date"] == previous + timedelta(days=1):
                    segment.append(item)
                else:
                    result.append(self._make_segment(segment))
                    segment = [item]
                previous = item["date"]
            if segment:
                result.append(self._make_segment(segment))

        result.sort(key=lambda x: (x["date_start"], str(x["model"]).lower(), str(x["garage_number"]).lower()))
        return result

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_report_data(self, date_from, date_to, repair_type=None):
        """Совместимый API.

        Без фильтра возвращает исходные карточки, с repair_type — точные
        фактические интервалы по дневной хронологии.
        """
        start, end = self._normalize_period(date_from, date_to)
        if repair_type:
            return {
                "date_from": start,
                "date_to": end,
                "rows": self.get_state_segments(start, end, repair_type),
            }
        rows = self.repository.get_work_for_period(start.isoformat(), end.isoformat())
        return {"date_from": start, "date_to": end, "rows": rows}

    def get_ktg(self, date_from, date_to):
        """КТГ по машино-дням на основе фактического состояния каждого дня."""
        start, end = self._normalize_period(date_from, date_to)
        equipment = list(self.repository.get_all_equipment())
        # Списанная техника не должна ухудшать КТГ действующего парка.
        active_equipment = [
            e for e in equipment
            if str(self._value(e, "status", "") or "").strip().lower() != "списан"
        ]
        equipment_ids = {self._value(e, "id") for e in active_equipment}
        total_equipment = len(active_equipment)
        period_days = (end - start).days + 1
        total_machine_days = total_equipment * period_days

        facts = [f for f in self.get_daily_timeline(start, end) if f["equipment_id"] in equipment_ids]
        unavailable_by_day = defaultdict(set)
        customer_by_day = defaultdict(set)
        for fact in facts:
            if fact["state"] in self.UNAVAILABLE_STATES:
                unavailable_by_day[fact["date"]].add(fact["equipment_id"])
            elif fact["state"] == "Работы заказчика":
                customer_by_day[fact["date"]].add(fact["equipment_id"])

        daily = []
        unavailable_machine_days = 0
        customer_machine_days = 0
        day = start
        while day <= end:
            unavailable = len(unavailable_by_day.get(day, set()))
            customer = len(customer_by_day.get(day, set()))
            available = max(0, total_equipment - unavailable)
            unavailable_machine_days += unavailable
            customer_machine_days += customer
            daily.append({
                "date": day,
                "available": available,
                "unavailable": unavailable,
                "customer_work": customer,
                "ktg_percent": round((available / total_equipment * 100), 2) if total_equipment else 0.0,
            })
            day += timedelta(days=1)

        available_machine_days = max(0, total_machine_days - unavailable_machine_days)
        return {
            "date_from": start,
            "date_to": end,
            "total_equipment": total_equipment,
            "available_equipment": daily[-1]["available"] if daily else total_equipment,
            "unavailable_equipment": daily[-1]["unavailable"] if daily else 0,
            "customer_work_equipment": daily[-1]["customer_work"] if daily else 0,
            "period_days": period_days,
            "total_machine_days": total_machine_days,
            "unavailable_machine_days": unavailable_machine_days,
            "available_machine_days": available_machine_days,
            "customer_machine_days": customer_machine_days,
            "ktg_percent": round((available_machine_days / total_machine_days * 100), 2) if total_machine_days else 0.0,
            "daily": daily,
        }

    def get_downtime_report(self, date_from, date_to):
        """Только реальные дни со статусом «Простой», а не любой ремонт."""
        segments = self.get_state_segments(date_from, date_to, "Простой")
        for row in segments:
            row["repair_type"] = "Простой"
            row["downtime_days"] = row["days"]
        segments.sort(key=lambda x: (-x["downtime_days"], str(x["model"]).lower(), str(x["garage_number"]).lower()))
        return segments

    def get_repair_type_statistics(self, date_from, date_to):
        counter = Counter(f["state"] for f in self.get_daily_timeline(date_from, date_to))
        return [
            {"repair_type": state, "count": count}
            for state, count in sorted(counter.items(), key=lambda item: (-item[1], item[0].lower()))
        ]

    def get_executor_statistics(self, date_from, date_to):
        """Считает дни фактического участия исполнителя, а не шапки карточек."""
        counter = Counter()
        work_ids = defaultdict(set)
        for fact in self.get_daily_timeline(date_from, date_to):
            for name in self._split_executors(fact["executors"]):
                counter[name] += 1
                work_ids[name].add(fact["work_id"])
        return [
            {"executor": name, "work_count": len(work_ids[name]), "work_days": counter[name]}
            for name in sorted(counter, key=lambda n: (-counter[n], n.lower()))
        ]

    def get_equipment_statistics(self, date_from, date_to):
        facts = self.get_daily_timeline(date_from, date_to)
        statistics = {}
        today = date.today()
        for fact in facts:
            equipment_id = fact["equipment_id"]
            item = statistics.setdefault(equipment_id, {
                "equipment_id": equipment_id,
                "model": fact["model"],
                "serial_number": fact["serial_number"],
                "garage_number": fact["garage_number"],
                "work_ids": set(),
                "work_days": set(),
                "downtime_days": set(),
                "active_work_ids": set(),
            })
            item["work_ids"].add(fact["work_id"])
            item["work_days"].add(fact["date"])
            if fact["state"] in self.UNAVAILABLE_STATES:
                item["downtime_days"].add(fact["date"])
            if fact["in_progress"] and fact["date"] == min(today, self._normalize_period(date_from, date_to)[1]):
                item["active_work_ids"].add(fact["work_id"])

        result = []
        for item in statistics.values():
            result.append({
                "equipment_id": item["equipment_id"],
                "model": item["model"],
                "serial_number": item["serial_number"],
                "garage_number": item["garage_number"],
                "work_count": len(item["work_ids"]),
                "work_days": len(item["work_days"]),
                "downtime_days": len(item["downtime_days"]),
                "active_count": len(item["active_work_ids"]),
            })
        result.sort(key=lambda x: (-x["downtime_days"], -x["work_days"], str(x["model"]).lower(), str(x["garage_number"]).lower()))
        return result

    def get_dashboard(self, date_from, date_to):
        ktg = self.get_ktg(date_from, date_to)
        downtime = self.get_downtime_report(date_from, date_to)
        return {
            "date_from": ktg["date_from"],
            "date_to": ktg["date_to"],
            "ktg": ktg,
            "total_downtime_days": sum(item["downtime_days"] for item in downtime),
            "repair_types": self.get_repair_type_statistics(date_from, date_to),
            "downtime": downtime,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def normalize_state(cls, raw):
        value = str(raw or "").strip()
        low = value.lower().replace("ё", "е")
        if not low:
            return ""
        if "авар" in low:
            return "Аварийный ремонт"
        if "заказ" in low or "полюс" in low:
            return "Работы заказчика"
        if "монитор" in low:
            return "Мониторинг состояния"
        if "модерн" in low or "сборк" in low or "гарант" in low:
            return "Модернизация"
        if "прост" in low or low == ">":
            return "Простой"
        if low == "то" or low.startswith("то-") or "техническ" in low or "плановые то" in low:
            return "ТО"
        if "будущ" in low or "планируем" in low:
            return "Будущие работы"
        if "план" in low:
            return "Плановый ремонт"
        return value

    @staticmethod
    def _make_segment(items):
        first = items[0]
        last = items[-1]
        # Описание/исполнители берём из последних непустых фактических записей.
        description = next((x["description"] for x in reversed(items) if x["description"]), "")
        executors = next((x["executors"] for x in reversed(items) if x["executors"]), "")
        machine_hours = max((x["machine_hours"] for x in items), default=0)
        return {
            "work_id": first["work_id"],
            "equipment_id": first["equipment_id"],
            "model": first["model"],
            "serial_number": first["serial_number"],
            "garage_number": first["garage_number"],
            "request_number": first["request_number"],
            "repair_type": first["state"],
            "state": first["state"],
            "date_start": first["date"],
            "date_end": last["date"],
            "days": len(items),
            "machine_hours": machine_hours,
            "description": description,
            "executors": executors,
            "in_progress": bool(last["in_progress"]),
        }

    @staticmethod
    def _value(row, key, default=None):
        try:
            value = row[key]
        except Exception:
            try:
                value = row.get(key, default)
            except Exception:
                return default
        return default if value is None else value

    @staticmethod
    def _number(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _split_executors(value):
        normalized = str(value or "").replace(";", ",").replace("\n", ",")
        return [part.strip() for part in normalized.split(",") if part.strip()]

    @classmethod
    def _normalize_period(cls, date_from, date_to):
        start = cls._to_date(date_from)
        end = cls._to_date(date_to)
        return (end, start) if start > end else (start, end)

    @staticmethod
    def _to_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if not value:
            raise ValueError("Дата не указана.")
        raw = str(value).strip()
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return date.fromisoformat(raw[:10])
