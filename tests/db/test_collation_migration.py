import importlib
from types import SimpleNamespace


class FakeResult:
    def __init__(self, row):
        self.row = row

    def one(self):
        return self.row


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.statements = []
        self.options = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execution_options(self, **options):
        self.options = options
        return self

    def execute(self, statement):
        sql = str(statement)
        self.statements.append(sql)
        if sql.lstrip().upper().startswith("SELECT"):
            return FakeResult(self.row)
        return SimpleNamespace()


class FakeEngine:
    def __init__(self, row):
        self.connection = FakeConnection(row)
        self.dialect = SimpleNamespace(
            identifier_preparer=SimpleNamespace(quote=lambda value: f'"{value}"')
        )

    def connect(self):
        return self.connection


def migration():
    return importlib.import_module(
        "backend.db.migrations.0005_refresh_database_collation"
    )


def test_collation_migration_skips_database_at_current_version():
    active_engine = FakeEngine(("lexsync", "2.41", "2.41"))

    migration().upgrade(active_engine)

    assert len(active_engine.connection.statements) == 1
    assert active_engine.connection.options == {"isolation_level": "AUTOCOMMIT"}


def test_collation_migration_reindexes_before_refreshing_version():
    active_engine = FakeEngine(("lexsync", "2.36", "2.41"))

    migration().upgrade(active_engine)

    assert active_engine.connection.statements[1:] == [
        'REINDEX DATABASE CONCURRENTLY "lexsync"',
        'ALTER DATABASE "lexsync" REFRESH COLLATION VERSION',
    ]


def test_collation_migration_does_not_refresh_or_break_startup_when_reindex_fails():
    active_engine = FakeEngine(("lexsync", "2.36", "2.41"))
    original_execute = active_engine.connection.execute

    def execute(statement):
        if str(statement).startswith("REINDEX"):
            raise RuntimeError("database is busy")
        return original_execute(statement)

    active_engine.connection.execute = execute

    migration().upgrade(active_engine)

    assert all(
        not sql.startswith("ALTER DATABASE")
        for sql in active_engine.connection.statements
    )
