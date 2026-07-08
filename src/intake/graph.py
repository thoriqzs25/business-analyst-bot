import json
import time
from typing import TypedDict, Literal

from langgraph.graph import StateGraph, START, END

from src.intake.schema import BusinessProfile
from src.llm import chat
from src.mem0_client import search_memory, add_memory
from src.config import settings
from src.token_tracker import log_token_usage


class BAState(TypedDict):
    user_id: str
    profile: dict
    last_bot_message: str
    last_activity: float
    conversation: list


INACTIVITY_TIMEOUT = 900  # 15 minutes

SYSTEM_PROMPT = """Kamu adalah asisten bisnis yang membantu pemilik usaha kecil dan menengah di Indonesia. 

Tugasmu:
1. Mengobrol dengan ramah dalam Bahasa Indonesia yang santai dan mudah dipahami
2. Mengumpulkan data profil bisnis secara alami melalui percakapan
3. Menjawab pertanyaan seputar bisnis sederhana

Profil bisnis yang perlu dikumpulkan:
- nama_usaha: Nama bisnis/usaha
- bidang: Industri/bidang usaha
- omzet: Kisaran omzet per bulan
- jumlah_tim: Jumlah karyawan/tim
- lokasi: Kota/lokasi usaha
- kendala: Masalah atau kendala yang dihadapi
- tujuan: Tujuan atau target bisnis

Cara merespon:
- Jika profil belum lengkap, tanyakan informasi yang kurang dengan santai
- Jika user sudah memberi semua informasi, ringkas dan konfirmasi
- Jika user bertanya, jawab dengan ramah
- Jangan terlalu formal, gunakan bahasa sehari-hari
- Jangan menanyakan semua informasi sekaligus, tanya satu per satu secara alami

Jika user tidak aktif selama 15 menit dan kembali chat, ingatkan topik terakhir yang dibahas.

Gunakan profile_belum_lengkap, profile_lengkap, or tanya_jawab sebagai mode.
"""


def build_ba_graph():
    workflow = StateGraph(BAState)

    workflow.add_node("process_message", process_message_node)
    workflow.add_edge(START, "process_message")
    workflow.add_conditional_edges(
        "process_message",
        decide_next,
        {"lanjut": "process_message", "selesai": END},
    )

    return workflow.compile()


async def process_message_node(state: BAState) -> BAState:
    user_id = state["user_id"]
    profile = BusinessProfile(**state.get("profile", {}))
    conversation = list(state.get("conversation", []))
    last_activity = state.get("last_activity", 0.0)
    last_bot_message = state.get("last_bot_message", "")

    now = time.time()

    relevant = search_memory(user_id, conversation[-1]["content"] if conversation else "")
    memory_text = "\n".join(f"- {m['memory']}" for m in relevant) if relevant else "Belum ada memori."

    profile_summary = profile.model_dump_json(indent=2)

    inactivity_warning = ""
    if last_activity and (now - last_activity) > INACTIVITY_TIMEOUT and last_bot_message:
        inactivity_warning = (
            f"\nCATATAN: User ini tidak aktif selama lebih dari 15 menit. "
            f"Pesan terakhir bot adalah: '{last_bot_message}'. "
            f"Sapa kembali dan tanyakan apakah ingin melanjutkan diskusi sebelumnya."
        )

    history_text = ""
    for msg in conversation[-6:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_text += f"{'User' if role == 'user' else 'Bot'}: {content}\n"

    user_message = conversation[-1]["content"] if conversation else ""

    system = SYSTEM_PROMPT + f"""

=== PROFIL BISNIS SAAT INI ===
{profile_summary}

=== MEMORI USER ===
{memory_text}

=== RIWAYAT PERCAKAPAN ===
{history_text}
{inactivity_warning}

RESPON dalam Bahasa Indonesia yang santai.
Setelah merespon, tambahkan baris terakhir dengan JSON:
---BEGIN PROFILE UPDATE---
{{"mode": "profile_belum_lengkap" | "profile_lengkap" | "tanya_jawab", "field_updates": {{"nama_usaha": "...", ...}}}}
---END PROFILE UPDATE---

Hanya isi field_updates dengan informasi BARU yang didapat dari percakapan ini. Jangan timpa data yang sudah ada.
Jika tidak ada update, kirimkan {{}}.
"""

    response_text, prompt_tokens, completion_tokens = await chat(system, user_message)

    await log_token_usage(user_id, settings.llm_model, prompt_tokens, completion_tokens)

    bot_reply = response_text
    profile_update = {}

    if "---BEGIN PROFILE UPDATE---" in response_text:
        parts = response_text.split("---BEGIN PROFILE UPDATE---")
        bot_reply = parts[0].strip()
        json_part = parts[1].split("---END PROFILE UPDATE---")[0].strip()
        try:
            parsed = json.loads(json_part)
            profile_update = parsed.get("field_updates", {})

            if "nama_usaha" in profile_update and profile_update["nama_usaha"]:
                profile.business_name = profile_update["nama_usaha"]
            if "bidang" in profile_update and profile_update["bidang"]:
                profile.industry = profile_update["bidang"]
            if "omzet" in profile_update and profile_update["omzet"]:
                profile.revenue_range = profile_update["omzet"]
            if "jumlah_tim" in profile_update and profile_update["jumlah_tim"]:
                profile.team_size = profile_update["jumlah_tim"]
            if "lokasi" in profile_update and profile_update["lokasi"]:
                profile.location = profile_update["lokasi"]
            if "kendala" in profile_update and profile_update["kendala"]:
                profile.pain_points = profile_update["kendala"]
            if "tujuan" in profile_update and profile_update["tujuan"]:
                profile.goals = profile_update["tujuan"]
        except json.JSONDecodeError:
            pass

    await add_memory(user_id, [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": bot_reply},
    ])

    conversation.append({"role": "assistant", "content": bot_reply})

    profile_complete = all([
        profile.business_name, profile.industry, profile.revenue_range,
        profile.team_size, profile.location,
    ])
    if profile_complete and not profile.intake_completed:
        profile.intake_completed = True

    return {
        "user_id": user_id,
        "profile": profile.model_dump(),
        "last_bot_message": bot_reply,
        "last_activity": now,
        "conversation": conversation,
    }


def decide_next(state: BAState) -> Literal["lanjut", "selesai"]:
    return "selesai"
