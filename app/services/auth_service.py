from datetime import UTC, datetime

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.core.errors import AuthError, ConflictError
from app.core.security import hash_password, verify_password
from app.db.mongo import get_db
from app.models.user import UserDoc


async def register_user(name: str, email: str, password: str) -> UserDoc:
    db = get_db()
    email = email.strip().lower()
    now = datetime.now(UTC)

    if await db.users.find_one({"email": email}):
        raise ConflictError("Email already registered", code="email_taken")

    doc = {
        "name": name.strip(),
        "email": email,
        "password_hash": hash_password(password),
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await db.users.insert_one(doc)
    except DuplicateKeyError:  # lost the race against the unique index
        raise ConflictError("Email already registered", code="email_taken") from None

    doc["_id"] = result.inserted_id
    return UserDoc.model_validate(doc)


async def authenticate_user(email: str, password: str) -> UserDoc:
    db = get_db()
    row = await db.users.find_one({"email": email.strip().lower()})
    if row is None or not verify_password(password, row["password_hash"]):
        raise AuthError("Invalid email or password", code="invalid_credentials")
    return UserDoc.model_validate(row)


async def get_user_by_id(user_id: str) -> UserDoc | None:
    if not ObjectId.is_valid(user_id):
        return None
    row = await get_db().users.find_one({"_id": ObjectId(user_id)})
    return UserDoc.model_validate(row) if row else None
