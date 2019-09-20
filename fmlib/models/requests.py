import logging

from pymodm import MongoModel, fields
from pymongo.errors import ServerSelectionTimeoutError
from ropod.structs.task import TaskPriority

from fmlib.models.users import User
from fmlib.utils.messages import Document


class Request(MongoModel):

    request_id = fields.UUIDField(primary_key=True)
    user_id = fields.ReferenceField(User)


class TaskRequest(Request):

    class Meta:
        archive_collection = 'task_request_archive'
        ignore_unknown_fields = True
        meta_model = "task-request"


class TransportationRequest(TaskRequest):

    pickup_location = fields.CharField()
    delivery_location = fields.CharField()
    earliest_pickup_time = fields.DateTimeField()
    latest_pickup_time = fields.DateTimeField()
    load_type = fields.CharField()
    load_id = fields.CharField()
    priority = fields.IntegerField(default=TaskPriority.NORMAL)
    hard_constraints = fields.BooleanField(default=True)
    _task_template = None

    def save(self):
        try:
            super().save(cascade=True)
        except ServerSelectionTimeoutError:
            logging.warning('Could not save models to MongoDB')

    @classmethod
    def from_payload(cls, payload):
        document = Document.from_payload(payload)
        document['_id'] = document.pop('request_id')
        request = TransportationRequest.from_document(document)
        request.save()
        return request

    def to_dict(self):
        dict_repr = self.to_son().to_dict()
        dict_repr.pop('_cls')
        dict_repr["request_id"] = str(dict_repr.pop('_id'))
        dict_repr["earliest_pickup_time"] = self.earliest_pickup_time.isoformat()
        dict_repr["latest_pickup_time"] = self.latest_pickup_time.isoformat()
        return dict_repr

    @property
    def meta_model(self):
        return self.Meta.meta_model
