from sqlalchemy.orm import Session

from app.chat.prompts import get_system_prompt
from app.models.user import User
from app.models.user_profile import UserProfile

LEVEL_INSTRUCTIONS: dict[str, dict[str, str]] = {
    "en": {
        "senior": "Keep answers concise and technical, do not re-explain basics.",
        "junior": "Be supportive and confirm the basics before going deeper.",
    },
    "pl": {
        "senior": "Odpowiadaj zwięźle i technicznie, nie powtarzaj podstaw.",
        "junior": "Bądź wspierający i utrwal najpierw podstawy.",
    },
}

PACE_INSTRUCTIONS: dict[str, dict[str, str]] = {
    "en": {
        "slow": "Explain step by step with short examples.",
        "fast": "Be brief and go straight to the point.",
    },
    "pl": {
        "slow": "Tłumacz krok po kroku i dodawaj krótkie przykłady.",
        "fast": "Bądź zwięzły i przechodź do sedna.",
    },
}

NAME_FALLBACKS = {"en": "new colleague", "pl": "nowy kolego"}


def get_profile(db: Session, user: User) -> UserProfile | None:
    return db.query(UserProfile).filter(UserProfile.user_id == user.id).first()


def get_display_name(user: User, profile: UserProfile | None, language: str) -> str:
    if profile is not None and profile.prefers_name:
        return profile.prefers_name
    if user.full_name:
        return user.full_name
    return NAME_FALLBACKS.get(language, NAME_FALLBACKS["en"])


def build_profile_context(user: User, profile: UserProfile | None, language: str) -> str:
    lines = [
        "[User profile]",
        f"Name: {get_display_name(user, profile, language)}",
        f"Role: {user.role}",
        f"Department: {user.department or 'unspecified'}",
    ]
    if profile is not None:
        lines.append(f"Experience level: {profile.experience_level}")
        lines.append(f"Learning pace: {profile.learning_pace}")
        if profile.interests:
            lines.append(f"Interests: {', '.join(profile.interests)}")
        if profile.custom_notes:
            lines.append(f"Notes: {profile.custom_notes}")
    return "\n".join(lines)


def personalize_instruction(user: User, profile: UserProfile | None, language: str) -> str:
    lang: str = language if language in LEVEL_INSTRUCTIONS else "en"
    instructions: list[str] = []
    if profile is not None:
        level_instruction = LEVEL_INSTRUCTIONS[lang].get(profile.experience_level)
        if level_instruction:
            instructions.append(level_instruction)
        pace_instruction = PACE_INSTRUCTIONS[lang].get(profile.learning_pace)
        if pace_instruction:
            instructions.append(pace_instruction)
    if not instructions:
        return ""
    return "[Personalization]\n" + "\n".join(instructions)


def build_system_prompt(language: str, user: User, profile: UserProfile | None) -> str:
    parts: list[str] = [get_system_prompt(language)]
    profile_context = build_profile_context(user, profile, language)
    if profile_context:
        parts.append(profile_context)
    instruction = personalize_instruction(user, profile, language)
    if instruction:
        parts.append(instruction)
    return "\n\n".join(parts)


def render_content(content: str, user: User, profile: UserProfile | None, language: str) -> str:
    name = get_display_name(user, profile, language)
    return content.replace("{name}", name)
