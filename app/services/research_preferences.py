"""Non-secret research defaults, shared by API and workers."""

from app.config import Settings
from app.contracts.research import ResearchPreferences, TopicProfile

DEFAULT_PATHS = [
    ["news", "esport", "fifa-online"],
    ["sport", "football"],
    ["sport", "tennis"],
    ["sport", "esport"],
    ["news", "technology"],
]


def preferences_path(settings=None):
    return (settings or Settings()).artifact_dir.resolve().parent / "settings" / "research.json"


def load_preferences(settings=None):
    path = preferences_path(settings)
    if path.exists():
        return ResearchPreferences.model_validate_json(path.read_text(encoding="utf-8"))
    return ResearchPreferences(
        profiles=[TopicProfile(branch="research", topic_path=path) for path in DEFAULT_PATHS]
    )


def save_preferences(preferences, settings=None):
    path = preferences_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(preferences.model_dump_json(indent=2), encoding="utf-8")
    temporary.replace(path)
    return preferences
