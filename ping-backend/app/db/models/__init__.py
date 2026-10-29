"""SQLAlchemy models. Importing this package registers every table on
`Base.metadata`, which Alembic's autogenerate needs.

    User -> Organization -> Bot -> BotSource (-> Memora source)
                                -> AllowedDomain
                                -> Visitor -> Conversation -> Message
                                -> Lead
"""

from app.db.models.auth_user import AuthenticatedUser
from app.db.models.bot import Bot
from app.db.models.conversation import Conversation, Lead, Message, Visitor
from app.db.models.domain import AllowedDomain
from app.db.models.live import AgentPresence, BotAnswer
from app.db.models.organization import Organization, OrganizationMember
from app.db.models.plan import Plan
from app.db.models.sharing import BotShare, Invitation
from app.db.models.source import BotSource
from app.db.models.users import Users

__all__ = [
    "Users",
    "AuthenticatedUser",
    "Organization",
    "OrganizationMember",
    "Plan",
    "BotShare",
    "Invitation",
    "AgentPresence",
    "BotAnswer",
    "Bot",
    "BotSource",
    "AllowedDomain",
    "Visitor",
    "Conversation",
    "Message",
    "Lead",
]
