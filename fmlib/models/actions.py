from pymodm import EmbeddedMongoModel, fields
from ropod.utils.uuid import generate_uuid


class Action(EmbeddedMongoModel):

    action_id = fields.UUIDField(primary_key=True, default=generate_uuid())
    type = fields.CharField()

    class Meta:
        ignore_unknown_fields = True


class GoTo(Action):

    locations = fields.ListField()
