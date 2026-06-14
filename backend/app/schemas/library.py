from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid


class LibraryEntryResponse(BaseModel):
    id: uuid.UUID
    brainstorm_id: uuid.UUID
    topic_id: Optional[uuid.UUID] = None
    folder_name: str
    file_name: str
    file_path: str
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LibraryFolderResponse(BaseModel):
    folder_name: str
    entries: List[LibraryEntryResponse]


class LibraryUpdateRequest(BaseModel):
    content: str
