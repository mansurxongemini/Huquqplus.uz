import os
import subprocess
from datetime import datetime, timezone
import openpyxl
import pytest

from scripts.generate_report import parse_date, get_preset_range
from src.app.generate_staff_report import generate_comprehensive_report


def test_parse_date():
    # DD.MM.YYYY
    dt_start = parse_date("01.08.2026", is_end=False)
    assert dt_start.year == 2026
    assert dt_start.month == 8
    assert dt_start.day == 1
    assert dt_start.hour == 0
    assert dt_start.minute == 0
    assert dt_start.tzinfo == timezone.utc

    dt_end = parse_date("30.09.2026", is_end=True)
    assert dt_end.year == 2026
    assert dt_end.month == 9
    assert dt_end.day == 30
    assert dt_end.hour == 23
    assert dt_end.minute == 59
    assert dt_end.tzinfo == timezone.utc

    # YYYY-MM-DD
    dt_iso = parse_date("2026-08-15")
    assert dt_iso.year == 2026
    assert dt_iso.month == 8
    assert dt_iso.day == 15

    # Invalid format raises ValueError
    with pytest.raises(ValueError):
        parse_date("invalid-date")


def test_get_preset_range():
    start, end = get_preset_range("today")
    assert start.date() == end.date()
    assert start.hour == 0
    assert end.hour == 23

    start_m, end_m = get_preset_range("month")
    assert start_m.day == 1


def test_generate_comprehensive_report_with_date_range():
    start_dt = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc)

    file_path, summary = generate_comprehensive_report(date_range=(start_dt, end_dt))
    assert os.path.exists(file_path)
    assert "total_inquiries" in summary
    assert "total_appointments" in summary
    assert "top_regions" in summary

    # Verify Excel workbook structure
    wb = openpyxl.load_workbook(file_path)
    expected_sheets = [
        "Umumiy loyiha statistikasi",
        "Hududlar va Demografiya",
        "Huquqiy Sohalar Tahlili",
        "Mutaxassislar KPI",
        "Murojaatlar Registri",
        "Yurist Qabullari"
    ]
    assert wb.sheetnames == expected_sheets


def test_cli_execution():
    out_file = "reports/test_cli_report.xlsx"
    if os.path.exists(out_file):
        os.remove(out_file)

    res = subprocess.run(
        ["python3", "scripts/generate_report.py", "01.08.2026", "30.09.2026", "-o", out_file],
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert os.path.exists(out_file)
    assert "HUQUQPLUS — KENG QAMROVLI TAHLILIY HISOBOT" in res.stdout
    assert "Hisobot muvaffaqiyatli tayyorlandi" in res.stdout
