from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.common import PyObjectId


class UserDoc(BaseModel):
    """Shape of a document in the `users` collection."""

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    name: str
    email: EmailStr
    password_hash: str
    created_at: datetime
    updated_at: datetime
