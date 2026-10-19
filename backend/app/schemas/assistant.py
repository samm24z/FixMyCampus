"""Campus assistant chat schemas. Actions are proposals: the page runs them only after a click."""

from typing import Annotated, List, Literal, Optional, Union
from pydantic import BaseModel, Field
from app.models.enums import PriorityEnum


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(..., max_length=2000)


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    history: List[ChatTurn] = Field(default_factory=list, max_length=8)


class AssistantSource(BaseModel):
    n: int
    title: str
    url: str
    section: str


class ReportProblemAction(BaseModel):
    type: Literal["report_problem"] = "report_problem"
    title: str
    description: str
    category: str
    location: str = ""
    priority: PriorityEnum = PriorityEnum.MEDIUM


class TicketAction(BaseModel):
    """Confirm fixed, reopen or cancel one of the signed-in user's own tickets."""

    type: Literal["confirm_fixed", "reopen_ticket", "cancel_ticket"]
    ticket_number: str
    ticket_title: str


class AddCommentAction(BaseModel):
    type: Literal["add_comment"] = "add_comment"
    ticket_number: str
    ticket_title: str
    text: str


class ContactAction(BaseModel):
    type: Literal["contact"] = "contact"
    label: str
    email: Optional[str] = None
    phone: Optional[str] = None


class OpenLinkAction(BaseModel):
    type: Literal["open_link"] = "open_link"
    label: str
    url: str


AssistantAction = Annotated[
    Union[ReportProblemAction, TicketAction, AddCommentAction, ContactAction, OpenLinkAction],
    Field(discriminator="type"),
]


class AssistantChatResponse(BaseModel):
    answer: str
    sources: List[AssistantSource] = Field(default_factory=list)
    actions: List[AssistantAction] = Field(default_factory=list)
    status: Literal["answered", "not_found", "fallback"]
