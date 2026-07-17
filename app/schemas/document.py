from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    chat_id: str
    filename: str
    content_type: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
