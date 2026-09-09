from app.core.config import Settings


def test_dsn_passthrough_without_credentials():
    s = Settings(mongodb_uri="mongodb://localhost:27017", mongodb_username="", mongodb_password="")
    assert s.mongo_dsn == "mongodb://localhost:27017"


def test_dsn_injects_and_encodes_credentials():
    s = Settings(
        mongodb_uri="mongodb+srv://cluster0.uelftlc.mongodb.net",
        mongodb_username="user@corp",
        mongodb_password="p@ss/w:rd",
    )
    assert s.mongo_dsn == (
        "mongodb+srv://user%40corp:p%40ss%2Fw%3Ard@cluster0.uelftlc.mongodb.net"
    )


def test_dsn_replaces_credentials_already_in_uri():
    s = Settings(
        mongodb_uri="mongodb+srv://old:creds@cluster0.uelftlc.mongodb.net",
        mongodb_username="new",
        mongodb_password="secret",
    )
    assert s.mongo_dsn == "mongodb+srv://new:secret@cluster0.uelftlc.mongodb.net"
