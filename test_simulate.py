"""
Simulasi percakapan dengan Business Analyst Bot.

Cara pakai:
1. Set OPENCODE_GO_API_KEY di .env
2. Jalankan `docker compose up -d redis postgres qdrant`
3. python test_simulate.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("OPENCODE_GO_API_KEY", "")
if not api_key:
    print("=" * 60)
    print("ERROR: OPENCODE_GO_API_KEY belum diisi!")
    print("1. Daftar/subscribe OpenCode Go di https://opencode.ai/go")
    print("2. Dapatkan API key dari https://opencode.ai/auth")
    print("3. Masukkan ke file .env: OPENCODE_GO_API_KEY=sk-...")
    print("=" * 60)
    sys.exit(1)


async def main():
    from src.intake.schema import BusinessProfile
    from src.agents.business_analyst import process_message
    from src.token_tracker import init_db
    from src.redis_client import init_redis

    await init_db()
    await init_redis()

    user_id = "62812xxxx@s.whatsapp.net"

    print("\n" + "=" * 60)
    print("SIMULASI BUSINESS ANALYST BOT")
    print("Bahasa: Indonesia")
    print("Model: deepseek-v4-flash")
    print("Tekan Ctrl+C untuk keluar")
    print("=" * 60 + "\n")

    # Sapa bot dulu
    messages = [
        "Halo",
        "Usaha saya warung sembako di Jakarta",
        "Omset sekitar 30-50 juta per bulan",
        "Saya sendiri aja yang jaga",
        "Kendala saya susah cari supplier murah",
        "Pengennya bisa jualan online juga sih",
    ]

    print("=== SIMULASI INTAKE FLOW ===\n")

    for msg in messages:
        print(f"🧑 USER: {msg}")
        print("   (memproses...)", end=" ", flush=True)
        await process_message(user_id, msg)
        print("✓\n")

    # Tes Q&A
    print("=== SIMULASI TANYA JAWAB ===\n")
    qa_messages = [
        "Menurutmu, apa yang harus saya lakukan untuk mulai jualan online?",
    ]

    for msg in qa_messages:
        print(f"🧑 USER: {msg}")
        print("   (memproses...)", end=" ", flush=True)
        await process_message(user_id, msg)
        print("✓\n")

    # Lihat profil
    from src.token_tracker import get_session
    from src.models.business_profile import BusinessProfile as ProfileModel
    from sqlalchemy import select

    print("=== PROFIL BISNIS TERSIMPAN ===\n")
    try:
        async with get_session() as session:
            result = await session.execute(
                select(ProfileModel).where(ProfileModel.user_id == user_id)
            )
            row = result.scalar_one_or_none()
            if row:
                for field in ["business_name", "industry", "revenue_range",
                              "team_size", "location", "pain_points", "goals"]:
                    val = getattr(row, field, "")
                    if val:
                        print(f"  {field}: {val}")
        print()
    except Exception as e:
        print(f"  (Database belum siap: {e})\n")


if __name__ == "__main__":
    asyncio.run(main())
