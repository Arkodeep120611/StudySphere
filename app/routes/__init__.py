from .account import bp as account_bp
from .analytics import bp as analytics_bp
from .auth import bp as auth_bp
from .chat import bp as chat_bp
from .documents import bp as documents_bp
from .flashcards import cards_bp, decks_bp
from .pages import bp as pages_bp
from .quizzes import bp as quizzes_bp


def register_blueprints(app):
    for blueprint in (
        auth_bp,
        pages_bp,
        documents_bp,
        quizzes_bp,
        decks_bp,
        cards_bp,
        chat_bp,
        analytics_bp,
        account_bp,
    ):
        app.register_blueprint(blueprint)
