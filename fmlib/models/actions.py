from pymodm import EmbeddedMongoModel, fields, MongoModel
from ropod.structs.status import ActionStatus


class Action(MongoModel, EmbeddedMongoModel):

    action_id = fields.UUIDField(primary_key=True)
    type = fields.CharField()

    class Meta:
        ignore_unknown_fields = True


class GoTo(Action):

    locations = fields.ListField()


class ActionProgress(EmbeddedMongoModel):
    action = fields.ReferenceField(Action)
    status = fields.IntegerField(default=ActionStatus.PLANNED)
