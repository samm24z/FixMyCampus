"""System enums for Roles, Ticket Statuses, Priorities, and Categories."""

import enum


class RoleEnum(str, enum.Enum):
    STUDENT = "STUDENT"
    FACULTY = "FACULTY"
    STAFF = "STAFF"
    COORDINATOR = "COORDINATOR"
    ADMIN = "ADMIN"


class TicketStatusEnum(str, enum.Enum):
    NEW = "NEW"
    UNDER_REVIEW = "UNDER_REVIEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    REOPENED = "REOPENED"
    CLOSED = "CLOSED"


class PriorityEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CategoryEnum(str, enum.Enum):
    IT_NETWORK = "IT / Network"
    ELECTRICAL = "Electrical"
    SANITATION = "Sanitation"
    WATER_PLUMBING = "Water / Plumbing"
    CLASSROOM_EQUIPMENT = "Classroom Equipment"
    CIVIL_MAINTENANCE = "Civil Maintenance"
    ACADEMIC_FACILITIES = "Academic Facilities"
    OTHER = "Other"


class NotificationTypeEnum(str, enum.Enum):
    TICKET_CREATED = "TICKET_CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    ASSIGNED = "ASSIGNED"
    SLA_BREACH = "SLA_BREACH"
    FEEDBACK_REQUEST = "FEEDBACK_REQUEST"
    COMMENT_ADDED = "COMMENT_ADDED"


class AuditActionEnum(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    STATUS_CHANGE = "STATUS_CHANGE"
    ASSIGNMENT = "ASSIGNMENT"
    AI_OVERRIDE = "AI_OVERRIDE"
    FEEDBACK_SUBMITTED = "FEEDBACK_SUBMITTED"
