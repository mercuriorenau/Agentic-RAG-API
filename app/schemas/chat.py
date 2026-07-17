from pydantic import BaseModel, Field


class ChatCreate(BaseModel):
    title: str = Field(default="New chat", min_length=1, max_length=200)


class ChatUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ChatResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ChatListResponse(BaseModel):
    chats: list[ChatResponse]


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    metadata: dict | None = None
    created_at: str


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
