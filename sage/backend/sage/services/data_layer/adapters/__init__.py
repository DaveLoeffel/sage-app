"""Entity adapters for converting between SQLAlchemy models and IndexedEntity."""

from sage.services.data_layer.adapters.base import BaseEntityAdapter
from sage.services.data_layer.adapters.email import EmailAdapter
from sage.services.data_layer.adapters.contact import ContactAdapter
from sage.services.data_layer.adapters.followup import FollowupAdapter
from sage.services.data_layer.adapters.meeting import MeetingAdapter
from sage.services.data_layer.adapters.generic import GenericAdapter

__all__ = [
    "BaseEntityAdapter",
    "EmailAdapter",
    "ContactAdapter",
    "FollowupAdapter",
    "MeetingAdapter",
    "GenericAdapter",
]
