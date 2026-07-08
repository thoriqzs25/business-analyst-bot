import logging
import time

from src.redis_client import publish
from src.intake.graph import build_ba_graph, BAState, INACTIVITY_TIMEOUT
from src.intake.schema import BusinessProfile

logger = logging.getLogger(__name__)

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_ba_graph()
    return _graph


async def process_message(user_id: str, message: str):
    graph = get_graph()

    profile = await _load_profile(user_id)

    initial_state: BAState = {
        "user_id": user_id,
        "profile": profile.model_dump(),
        "last_bot_message": "",
        "last_activity": 0.0,
        "conversation": [{"role": "user", "content": message}],
    }

    try:
        result = await graph.ainvoke(
            initial_state,
            {"configurable": {"thread_id": user_id,
                              "user_id": user_id}},
        )

        bot_reply = result.get("last_bot_message", "Maaf, ada gangguan. Coba lagi ya.")

        await _save_profile(user_id, BusinessProfile(**result.get("profile", {})))

        await publish("wa:outgoing", {
            "to": user_id,
            "body": bot_reply,
            "type": "text",
        })

        logger.info("Replied to %s: %.60s", user_id, bot_reply)

    except Exception as e:
        logger.error("Agent error for %s: %s", user_id, e, exc_info=True)
        await publish("wa:outgoing", {
            "to": user_id,
            "body": "Maaf, ada gangguan sistem. Coba lagi ya.",
            "type": "text",
        })


async def _load_profile(user_id: str) -> BusinessProfile:
    try:
        from src.token_tracker import get_session
        from src.models.business_profile import BusinessProfile as ProfileModel
        from sqlalchemy import select

        async with get_session() as session:
            result = await session.execute(
                select(ProfileModel).where(ProfileModel.user_id == user_id)
            )
            row = result.scalar_one_or_none()
            if row:
                return BusinessProfile(
                    business_name=row.business_name or "",
                    industry=row.industry or "",
                    revenue_range=row.revenue_range or "",
                    team_size=row.team_size or "",
                    location=row.location or "",
                    pain_points=row.pain_points or "",
                    goals=row.goals or "",
                    phone=row.phone or "",
                    intake_completed=row.intake_completed or False,
                )
    except Exception as e:
        logger.warning("Could not load profile for %s: %s", user_id, e)

    return BusinessProfile(phone=user_id)


async def _save_profile(user_id: str, profile: BusinessProfile):
    try:
        from src.token_tracker import get_session
        from src.models.business_profile import BusinessProfile as ProfileModel
        from sqlalchemy import select

        async with get_session() as session:
            result = await session.execute(
                select(ProfileModel).where(ProfileModel.user_id == user_id)
            )
            row = result.scalar_one_or_none()
            if row:
                row.business_name = profile.business_name
                row.industry = profile.industry
                row.revenue_range = profile.revenue_range
                row.team_size = profile.team_size
                row.location = profile.location
                row.pain_points = profile.pain_points
                row.goals = profile.goals
                row.intake_completed = profile.intake_completed
            else:
                session.add(ProfileModel(
                    user_id=user_id,
                    business_name=profile.business_name,
                    industry=profile.industry,
                    revenue_range=profile.revenue_range,
                    team_size=profile.team_size,
                    location=profile.location,
                    pain_points=profile.pain_points,
                    goals=profile.goals,
                    phone=profile.phone,
                    intake_completed=profile.intake_completed,
                ))
            await session.commit()
    except Exception as e:
        logger.warning("Could not save profile for %s: %s", user_id, e)
