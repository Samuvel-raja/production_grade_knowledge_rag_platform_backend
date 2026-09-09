from typing import Annotated

from pydantic import BeforeValidator

# Mongo ObjectId <-> str. Applied to `_id` and any id-bearing field so the rest of
# the app (and JSON responses) only ever sees strings.
PyObjectId = Annotated[str, BeforeValidator(str)]
