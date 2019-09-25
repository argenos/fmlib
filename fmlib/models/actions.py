from pymodm import EmbeddedMongoModel, fields


class Action(EmbeddedMongoModel):

    action_id = fields.UUIDField(primary_key=True)
    type = fields.CharField()

    class Meta:
        ignore_unknown_fields = True


class GoTo(Action):

    locations = fields.ListField()
