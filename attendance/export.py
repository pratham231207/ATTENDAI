"""
attendance/export.py — turn attendance rollup rows into the CSV format
requested in the spec:

    Student ID,Name,Class,Observed,Total Snapshots,Coverage,Status
"""

import io
import csv

from database import db


def attendance_rows_to_csv_dicts(attendance_rows: list, class_name: str = "") -> list:
    """
    Convert raw `database.db.get_attendance_for_session()` rows into the
    flat dict shape used for CSV export / display tables. Applies any
    manual teacher override to the Status column.
    """
    out = []
    for r in attendance_rows:
        out.append(
            {
                "Student ID": r["student_id"],
                "Name": r["name"],
                "Class": class_name or r.get("section", ""),
                "Observed": r["observation_count"],
                "Total Snapshots": r["total_snapshots"],
                "Coverage": f"{r['coverage_pct']:.0f}%",
                "Status": db.get_effective_status(r),
            }
        )
    return out


def to_csv_bytes(rows: list) -> bytes:
    """Serialize a list of flat dicts (as produced above) to CSV bytes."""
    if not rows:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")
