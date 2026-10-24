"""Importing this package registers every model on ``Base.metadata`` (needed for ``create_all``)."""

from app.models.beacon import Beacon
from app.models.beacon_message import BeaconMessage
from app.models.beacon_update import BeaconUpdate
from app.models.report import Evidence, Report, ReportConversation, ReportPriority, ReportStateTracking, ReportStatus, SenderType

__all__ = [
    "Beacon",
    "BeaconMessage",
    "BeaconUpdate",
    "Evidence",
    "Report",
    "ReportConversation",
    "ReportPriority",
    "ReportStateTracking",
    "ReportStatus",
    "SenderType",
]
