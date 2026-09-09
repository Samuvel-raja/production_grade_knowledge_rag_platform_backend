from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import PyObjectId


class WorkspaceDoc(BaseModel):
    """Shape of a document in the `workspaces` collection."""

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    name: str
    owner_id: PyObjectId
    # Present from day one so multi-member workspaces are a query change, not a
    # migration. Phase 1 always sets this to [owner_id].
    member_ids: list[PyObjectId] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
