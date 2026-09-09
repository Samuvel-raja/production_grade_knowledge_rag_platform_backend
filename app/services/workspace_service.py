from datetime import UTC, datetime

from bson import ObjectId

from app.core.errors import BadRequestError, ForbiddenError, NotFoundError
from app.db.mongo import get_db
from app.models.user import UserDoc
from app.models.workspace import WorkspaceDoc


def _can_access(workspace: WorkspaceDoc, user: UserDoc) -> bool:
    return user.id == workspace.owner_id or user.id in workspace.member_ids


async def create_workspace(name: str, owner: UserDoc) -> WorkspaceDoc:
    db = get_db()
    owner_oid = ObjectId(owner.id)
    now = datetime.now(UTC)
    doc = {
        "name": name.strip(),
        "owner_id": owner_oid,
        "member_ids": [owner_oid],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.workspaces.insert_one(doc)
    doc["_id"] = result.inserted_id
    return WorkspaceDoc.model_validate(doc)


async def list_workspaces(user: UserDoc) -> list[WorkspaceDoc]:
    uid = ObjectId(user.id)
    cursor = get_db().workspaces.find(
        {"$or": [{"owner_id": uid}, {"member_ids": uid}]}
    ).sort("created_at", -1)
    return [WorkspaceDoc.model_validate(row) async for row in cursor]


async def get_workspace(workspace_id: str, user: UserDoc) -> WorkspaceDoc:
    if not ObjectId.is_valid(workspace_id):
        raise BadRequestError("Invalid workspace id", code="invalid_id")

    row = await get_db().workspaces.find_one({"_id": ObjectId(workspace_id)})
    if row is None:
        raise NotFoundError("Workspace not found")

    workspace = WorkspaceDoc.model_validate(row)
    if not _can_access(workspace, user):
        raise ForbiddenError("You do not have access to this workspace", code="not_a_member")
    return workspace
