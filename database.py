from sqlalchemy.orm.session import Session


class ImprovedSession(Session):
    def insert_or_replace(self, model_instance):
        table = model_instance.__table__
        result = self.execute(
            table.insert().prefix_with("OR REPLACE"),
            {col: getattr(model_instance, col) for col in map(lambda x: x.name, table.columns)}
        )
        return result
