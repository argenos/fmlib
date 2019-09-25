from fmlib.models.environment import Position
from pymodm import EmbeddedMongoModel, fields, MongoModel
from pymodm.manager import Manager
from pymodm.queryset import QuerySet
from ropod.structs.status import AvailabilityStatus

from fmlib.models.actions import Action
from fmlib.models.tasks import Task


class ComponentStatus(EmbeddedMongoModel):
    pass


class CurrentTask(EmbeddedMongoModel):

    status = fields.CharField()
    task_id = fields.ReferenceField(Task)
    action_id = fields.ReferenceField(Action)


class Availability(EmbeddedMongoModel):

    status = fields.IntegerField(default=AvailabilityStatus.NO_COMMUNICATION, blank=True)
    current_task = fields.EmbeddedDocumentField(CurrentTask, default=None, blank=True)


class RobotStatus(EmbeddedMongoModel):

    availability = fields.EmbeddedDocumentField(Availability)
    component_status = fields.EmbeddedDocumentField(ComponentStatus)


class HardwareComponent(EmbeddedMongoModel):

    uuid = fields.UUIDField(primary_key=True)
    id = fields.CharField()
    model = fields.CharField()
    serial_number = fields.CharField(default='unknown')
    firmware_version = fields.CharField(default='unknown')
    version = fields.CharField(default='unknown')


class Wheel(HardwareComponent):
    pass


class Laser(HardwareComponent):
    pass


class RobotHardware(MongoModel):

    wheels = fields.EmbeddedDocumentListField(Wheel)
    laser = fields.EmbeddedDocumentListField(Laser)


class SoftwareComponent(EmbeddedMongoModel):

    name = fields.CharField(primary_key=True)
    package = fields.CharField()
    version = fields.CharField()


class SoftwareStack(MongoModel):

    navigation_stack = fields.EmbeddedDocumentListField(SoftwareComponent)
    interfaces = fields.EmbeddedDocumentListField(SoftwareComponent)


class Version(EmbeddedMongoModel):

    hardware = fields.EmbeddedDocumentField(RobotHardware)
    software = fields.EmbeddedDocumentField(SoftwareStack)


class RobotQuerySet(QuerySet):

    def get_robot(self, robot_id):
        return self.get({'_id': robot_id})


RobotManager = Manager.from_queryset(RobotQuerySet)


class Robot(MongoModel):

    robot_id = fields.CharField(primary_key=True)
    uuid = fields.UUIDField()
    version = fields.EmbeddedDocumentField(Version)
    # status = fields.EmbeddedDocumentField(RobotStatus)
    position = fields.EmbeddedDocumentField(Position)

    objects = RobotManager()

    class Meta:
        archive_collection = 'robot_archive'
        ignore_unknown_fields = True
