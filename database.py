from sqlalchemy.orm.session import Session
from contextlib import contextmanager


class ImprovedSession(Session):
    def insert_or_replace(self, model_instance):
        table = model_instance.__table__
        result = self.execute(
            table.insert().prefix_with("OR REPLACE"),
            {col: getattr(model_instance, col) for col in map(lambda x: x.name, table.columns)}
        )
        return result


@contextmanager
def use_session(session_cls, autocommit=False):
    db_session: ImprovedSession = session_cls()
    try:
        yield db_session
        if autocommit:
            db_session.commit()
    finally:
        db_session.close()
