#!/usr/bin/env python3
"""
HuquqPlus CLI Tahliliy Hisobot Generatori
Muallif: HuquqPlus jamoasi
Foydalanish:
    python scripts/generate_report.py 01.08.2026 30.09.2026
    python scripts/generate_report.py --start 2026-08-01 --end 2026-09-30
    python scripts/generate_report.py --preset month
    python scripts/generate_report.py --all
"""

import sys
import os
import shutil
import argparse
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

# Project root path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.app.generate_staff_report import (
    generate_comprehensive_report,
    parse_date,
    get_preset_range,
    parse_date_range_string,
)


def print_dashboard(summary: dict, period_str: str, file_path: str):
    """Terminalda chiroyli va tushunarli formatda tahliliy hisobotni ko'rsatadi"""
    tot_inq = summary.get("total_inquiries", 0)
    tot_ans = summary.get("total_answered", 0)
    res_rate = summary.get("resolution_rate", 0.0)
    avg_r = summary.get("avg_rating", 0.0)
    tot_r = summary.get("total_rated", 0)
    csat = summary.get("satisfaction_rate", 0.0)
    avg_resp = summary.get("avg_response_str", "—")

    tot_app = summary.get("total_appointments", 0)
    comp_app = summary.get("completed_appointments", 0)
    rem_app = summary.get("remote_appointments", 0)
    inp_app = summary.get("in_person_appointments", 0)
    app_r = summary.get("avg_app_rating", 0.0)

    top_regions = summary.get("top_regions", [])
    top_sections = summary.get("top_sections", [])
    top_spec = summary.get("top_specialist")

    file_size_kb = os.path.getsize(file_path) / 1024 if os.path.exists(file_path) else 0

    width = 70
    border = "=" * width
    divider = "-" * width

    print("\n" + border)
    print(f"  📊  HUQUQPLUS — KENG QAMROVLI TAHLILIY HISOBOT (CLI)".center(width))
    print(border)
    print(f"  🗓  Hisobot davri: {period_str}")
    print(divider)

    print(f"  📈  MUROJAATLAR STATISTIKASI:")
    print(f"      • Jami kelib tushgan:          {tot_inq} ta")
    print(f"      • Javob berilgan (hal etilgan): {tot_ans} ta ({res_rate:.1f}%)")
    print(f"      • Fuqarolar qoniqish darajasi:  ⭐ {avg_r:.2f} / 5.0 (ijobiy: {csat:.1f}%, {tot_r} ta baho)")
    print(f"      • O'rtacha javob berish tezligi: ⚡️ {avg_resp}")
    print(divider)

    print(f"  🏢  YURIST QABULLARI:")
    print(f"      • Jami arizalar soni:           {tot_app} ta")
    print(f"      • Muvaffaqiyatli o'tkazilgan:   {comp_app} ta")
    print(f"      • Masofaviy (Online) qabullar:  {rem_app} ta")
    print(f"      • Shaxsan (Ofisda) qabullar:    {inp_app} ta")
    app_r_str = f"⭐ {app_r:.2f} / 5.0" if app_r > 0 else "baho yo'q"
    print(f"      • Suhbatlarning o'rtacha bahosi: {app_r_str}")
    print(divider)

    print(f"  📍  ENG KO'P MUROJAAT TUSHGAN HUDUDLAR (TOP):")
    if top_regions:
        for idx, (reg, r_data) in enumerate(top_regions[:5], 1):
            pct = (r_data["total"] / tot_inq * 100) if tot_inq > 0 else 0.0
            print(f"      {idx}. {reg:<25} {r_data['total']} ta ({pct:.1f}%)")
    else:
        print("      Ma'lumot mavjud emas")
    print(divider)

    print(f"  ⚖️  ENG KO'P SO'RALGAN HUQUQIY SOHALAR (TOP):")
    if top_sections:
        for idx, (sec, s_data) in enumerate(top_sections[:5], 1):
            pct = (s_data["total"] / tot_inq * 100) if tot_inq > 0 else 0.0
            print(f"      {idx}. {sec:<25} {s_data['total']} ta ({pct:.1f}%)")
    else:
        print("      Ma'lumot mavjud emas")
    print(divider)

    print(f"  🏆  ENG YUQORI NATIJA KO'RSATGAN MUTAXASSIS:")
    if top_spec:
        spec_r = f"⭐ {top_spec['avg_rating']}" if top_spec.get('avg_rating', 0) > 0 else "baho yo'q"
        print(f"      🥇 {top_spec['name']} ({top_spec['role']})")
        print(f"         🎯 KPI: {top_spec['kpi_score']} ball | {top_spec['inquiries_count']} ta javob ({spec_r})")
    else:
        print("      Hozircha natijalar mavjud emas")
    print(divider)

    print(f"  📁  EXCEL TAHLIL FAYLI:")
    print(f"      • Fayl manzili:  {file_path}")
    print(f"      • Hajmi:         {file_size_kb:.1f} KB")
    print(f"      • Varaqlar (6):  1) Umumiy statistika")
    print(f"                       2) Hududlar va Demografiya")
    print(f"                       3) Murojaat yo'nalishlari")
    print(f"                       4) Mutaxassislar KPI")
    print(f"                       5) Murojaatlar Ro'yxati")
    print(f"                       6) Yurist Qabullari")
    print(border + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="HuquqPlus boti bo'yicha berilgan sana oralig'ida batafsil tahliliy Excel (.xlsx) hisobotini generatsiya qilish.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Misollar:
  python scripts/generate_report.py 01.08.2026 30.09.2026
  python scripts/generate_report.py --start 2026-08-01 --end 2026-09-30
  python scripts/generate_report.py --preset month
  python scripts/generate_report.py --all
  python scripts/generate_report.py 01.08.2026 30.09.2026 -o reports/avgust_sentabr.xlsx
"""
    )

    parser.add_argument("start_date", nargs="?", help="Boshlanish sanasi (masalan: 01.08.2026 yoki 2026-08-01)")
    parser.add_argument("end_date", nargs="?", help="Tugash sanasi (masalan: 30.09.2026 yoki 2026-09-30)")
    parser.add_argument("--start", "-s", dest="flag_start", help="Boshlanish sanasi")
    parser.add_argument("--end", "-e", dest="flag_end", help="Tugash sanasi")
    parser.add_argument(
        "--preset", "-p",
        choices=["today", "yesterday", "week", "month", "last_month", "year"],
        help="Tayyor davrlar: today, yesterday, week, month, last_month, year"
    )
    parser.add_argument("--all", "-a", action="store_true", help="Barcha davr uchun (cheklovlarsiz)")
    parser.add_argument("--output", "-o", help="Natijaviy Excel fayli saqlanadigan yo'l (ixtiyoriy)")

    args = parser.parse_args()

    # Determine date range
    start_dt = None
    end_dt = None
    period_label = "Barcha davr"

    if args.preset:
        start_dt, end_dt = get_preset_range(args.preset)
        period_label = f"{start_dt.strftime('%d.%m.%Y')} – {end_dt.strftime('%d.%m.%Y')} ({args.preset})"
    elif args.all:
        start_dt, end_dt = None, None
        period_label = "Barcha davr (to'liq statistika)"
    else:
        start_arg = args.flag_start or args.start_date
        end_arg = args.flag_end or args.end_date

        if start_arg and not end_arg and ("#" in start_arg or " — " in start_arg or " - " in start_arg or ".." in start_arg):
            try:
                start_dt, end_dt, period_label, _ = parse_date_range_string(start_arg)
            except Exception as e:
                print(f"❌ Xatolik: {e}", file=sys.stderr)
                sys.exit(1)
        elif start_arg and end_arg:
            start_dt = parse_date(start_arg, is_end=False)
            end_dt = parse_date(end_arg, is_end=True)
            if start_dt > end_dt:
                print("❌ Xatolik: Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas!", file=sys.stderr)
                sys.exit(1)
            period_label = f"{start_dt.strftime('%d.%m.%Y')} – {end_dt.strftime('%d.%m.%Y')}"
        elif start_arg and not end_arg:
            start_dt = parse_date(start_arg, is_end=False)
            end_dt = datetime.now(timezone.utc).replace(hour=23, minute=59, second=59, microsecond=999999)
            period_label = f"{start_dt.strftime('%d.%m.%Y')} – bugungacha ({end_dt.strftime('%d.%m.%Y')})"
        else:
            # If no argument is passed, show help and prompt
            print("⚠️ Sana oralig'i ko'rsatilmadi!")
            print("Foydalanish misoli: python scripts/generate_report.py 01.08.2026 30.09.2026")
            print("Yoki: python scripts/generate_report.py 01.08.2026#30.09.2026")
            print("Yoki barcha davr uchun: python scripts/generate_report.py --all\n")
            parser.print_help()
            sys.exit(1)

    print(f"⏳ Tahliliy hisobot tayyorlanmoqda... Davr: {period_label}")

    try:
        from src.app.generate_staff_report import generate_comprehensive_report
        
        date_range = (start_dt, end_dt) if start_dt and end_dt else None
        generated_file, summary_dict = generate_comprehensive_report(date_range=date_range)

        # Handle destination file path
        if args.output:
            final_path = os.path.abspath(args.output)
            os.makedirs(os.path.dirname(final_path), exist_ok=True)
            shutil.copy2(generated_file, final_path)
        else:
            # Place in reports/ directory in project root by default for easy access
            reports_dir = os.path.join(BASE_DIR, "reports")
            os.makedirs(reports_dir, exist_ok=True)
            
            if start_dt and end_dt:
                file_tag = f"{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}"
            else:
                file_tag = "Barcha_davr"
            
            final_filename = f"HuquqPlus_Hisobot_{file_tag}.xlsx"
            final_path = os.path.join(reports_dir, final_filename)
            shutil.copy2(generated_file, final_path)

        # Print beautiful dashboard
        print_dashboard(summary_dict, period_label, final_path)
        print("✅ Hisobot muvaffaqiyatli tayyorlandi!")

    except Exception as e:
        print(f"\n❌ Hisobotni generatsiya qilishda xatolik yuz berdi: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
