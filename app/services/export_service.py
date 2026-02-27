from __future__ import annotations

import csv
from io import BytesIO, StringIO

from openpyxl import Workbook

from app.models import Registration
from app.models.enums import PersonRole, RegistrationStatus


class ExportService:
    @staticmethod
    def export_csv(registrations: list[Registration], only_confirmed: bool = False) -> bytes:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "registration_id",
                "event_id",
                "status",
                "team_name",
                "team_size",
                "role",
                "last_name",
                "first_name",
                "middle_name",
                "contact",
                "group_name",
                "is_not_mipt",
                "passport_series",
                "passport_number",
                "passport_issued_by",
                "passport_division_code",
                "passport_issue_date",
                "birth_date",
                "birth_place",
                "registration_address",
            ]
        )
        for reg in registrations:
            if only_confirmed and reg.status != RegistrationStatus.confirmed:
                continue
            for person in reg.people:
                writer.writerow(
                    [
                        reg.id,
                        reg.event_id,
                        reg.status.value,
                        reg.team_name or "",
                        reg.team_size or "",
                        person.role.value,
                        person.last_name,
                        person.first_name,
                        person.middle_name or "",
                        person.contact or "",
                        person.group_name or "",
                        "1" if person.is_not_mipt else "0",
                        person.passport_series or "",
                        person.passport_number or "",
                        person.passport_issued_by or "",
                        person.passport_division_code or "",
                        person.passport_issue_date.isoformat() if person.passport_issue_date else "",
                        person.birth_date.isoformat() if person.birth_date else "",
                        person.birth_place or "",
                        person.registration_address or "",
                    ]
                )
        return output.getvalue().encode("utf-8")

    @staticmethod
    def export_xlsx(registrations: list[Registration], only_confirmed: bool = False) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "registrations"
        ws.append(
            [
                "registration_id",
                "event_id",
                "status",
                "team_name",
                "team_size",
                "role",
                "last_name",
                "first_name",
                "middle_name",
                "contact",
                "group_name",
                "is_not_mipt",
                "passport_series",
                "passport_number",
                "passport_issued_by",
                "passport_division_code",
                "passport_issue_date",
                "birth_date",
                "birth_place",
                "registration_address",
            ]
        )

        for reg in registrations:
            if only_confirmed and reg.status != RegistrationStatus.confirmed:
                continue
            for person in reg.people:
                ws.append(
                    [
                        reg.id,
                        reg.event_id,
                        reg.status.value,
                        reg.team_name or "",
                        reg.team_size or "",
                        person.role.value,
                        person.last_name,
                        person.first_name,
                        person.middle_name or "",
                        person.contact or "",
                        person.group_name or "",
                        person.is_not_mipt,
                        person.passport_series or "",
                        person.passport_number or "",
                        person.passport_issued_by or "",
                        person.passport_division_code or "",
                        person.passport_issue_date.isoformat() if person.passport_issue_date else "",
                        person.birth_date.isoformat() if person.birth_date else "",
                        person.birth_place or "",
                        person.registration_address or "",
                    ]
                )

        payload = BytesIO()
        wb.save(payload)
        payload.seek(0)
        return payload.read()

    @staticmethod
    def export_passes_csv(registrations: list[Registration]) -> bytes:
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "event_id",
                "registration_id",
                "team_name",
                "role",
                "last_name",
                "first_name",
                "middle_name",
                "passport_series",
                "passport_number",
                "passport_issued_by",
                "passport_division_code",
                "passport_issue_date",
                "birth_date",
                "birth_place",
                "registration_address",
            ]
        )
        for reg in registrations:
            for person in reg.people:
                if not person.is_not_mipt:
                    continue
                if person.role not in (PersonRole.solo, PersonRole.captain, PersonRole.team_not_mipt_member):
                    continue
                writer.writerow(
                    [
                        reg.event_id,
                        reg.id,
                        reg.team_name or "",
                        person.role.value,
                        person.last_name,
                        person.first_name,
                        person.middle_name or "",
                        person.passport_series or "",
                        person.passport_number or "",
                        person.passport_issued_by or "",
                        person.passport_division_code or "",
                        person.passport_issue_date.isoformat() if person.passport_issue_date else "",
                        person.birth_date.isoformat() if person.birth_date else "",
                        person.birth_place or "",
                        person.registration_address or "",
                    ]
                )
        return output.getvalue().encode("utf-8")
