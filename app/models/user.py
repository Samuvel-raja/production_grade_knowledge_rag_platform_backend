from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.common import PyObjectId


class LLMConfig(BaseModel):
    """A user's own LLM credentials — overrides the server-wide default for
    every request they make, in any workspace.

    `encrypted_api_key` is ciphertext (see app.core.crypto); the plaintext key
    never touches the database and is never returned by the API.
    """

    provider: str
    model: str
    encrypted_api_key: str


class UserDoc(BaseModel):
    """Shape of a document in the `users` collection."""

    model_config = ConfigDict(populate_by_name=True)

    id: PyObjectId = Field(alias="_id")
    name: str
    email: EmailStr
    password_hash: str
    llm_config: LLMConfig | None = None
    created_at: datetime
    updated_at: datetime
