from ..extensions import db
from ..models import StudyActivity


def record_activity(user_id, kind, title, subject="General", score=None):
    """Queue a study activity row. The caller commits the session."""
    db.session.add(
        StudyActivity(
            user_id=user_id,
            kind=kind,
            title=title[:200],
            subject=(subject or "General")[:100],
            score=score,
        )
    )
