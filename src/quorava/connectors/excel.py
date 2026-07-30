from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from ..models import RawRow


class ExcelConnector:
    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> list[RawRow]:
        if not self.path.exists():
            raise FileNotFoundError(f"Excel source not found: {self.path}")
        workbook = load_workbook(self.path, read_only=True, data_only=True)
        rows: list[RawRow] = []
        try:
            for sheet in workbook.worksheets:
                iterator = sheet.iter_rows(values_only=True)
                headers = [str(value).strip() if value is not None else "" for value in next(iterator)]
                for row_index, values in enumerate(iterator, start=2):
                    payload = {headers[index]: value for index, value in enumerate(values) if headers[index]}
                    if not any(value not in (None, "") for value in payload.values()):
                        continue
                    rows.append(
                        RawRow(
                            source_type="excel",
                            source_ref=f"{self.path.name}:{sheet.title}:{row_index}",
                            source_row=row_index,
                            payload=payload,
                        )
                    )
        finally:
            workbook.close()
        return rows

