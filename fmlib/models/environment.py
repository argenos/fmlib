from pymodm import EmbeddedMongoModel, fields


class Position(EmbeddedMongoModel):

    x = fields.FloatField()
    y = fields.FloatField()
    theta = fields.FloatField()

    class Meta:
        ignore_unknown_fields = True
