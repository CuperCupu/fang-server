from peewee import Model, Field

from .database import db


class BaseEntity(Model):
    class Meta:
        database = db

    def to_dict(self, *projections):
        fields = []
        for projection in projections:
            if not isinstance(projection, Field):
                raise TypeError(
                    f"Invalid type '{projection.__class__.__name__}' for projection, expected '{Field.__name__}'")
            if not isinstance(self, projection.model):
                raise TypeError(f"Trying to project a field from other model '{projection.model}'")
            fields.append(projection.name)
        if fields:
            data = {}
            for field in fields:
                data[field] = self.__data__[field]
        else:
            data = dict(self.__data__)
        return data

    @classmethod
    def from_dict(cls, data):
        instance = cls()
        instance.__data__ = data
        return instance


def sync_tables():
    db.create_tables(BaseEntity.__subclasses__())
