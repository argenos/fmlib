import logging
import uuid
from datetime import datetime, timedelta

import dateutil.parser
from pymodm import EmbeddedMongoModel, fields, MongoModel
from pymodm.context_managers import switch_collection
from pymodm.errors import DoesNotExist
from pymodm.manager import Manager
from pymodm.queryset import QuerySet
from pymongo.errors import ServerSelectionTimeoutError
from ropod.structs.status import ActionStatus, TaskStatus as TaskStatusConst
from ropod.utils.timestamp import TimeStamp

from fmlib.models.actions import Action, ActionProgress
from fmlib.models.requests import TaskRequest
from fmlib.utils.messages import Document
from fmlib.utils.messages import Message


class TaskQuerySet(QuerySet):

    def get_task(self, task_id):
        """Return a task object matching to a task_id.
        """
        if isinstance(task_id, str):
            task_id = uuid.UUID(task_id)

        return self.get({'_id': task_id})


class TaskStatusQuerySet(QuerySet):

    def by_status(self, status):
        return self.raw({"status": status})

    def unallocated(self):
        return self.raw({"status": TaskStatusConst.UNALLOCATED})

    def allocated(self):
        return self.raw({"status": TaskStatusConst.ALLOCATED})

    def planned(self):
        return self.raw({"status": TaskStatusConst.PLANNED})

    def scheduled(self):
        return self.raw({"status": TaskStatusConst.SCHEDULED})

    def shipped(self):
        return self.raw({"status": TaskStatusConst.DISPATCHED})

    def ongoing(self):
        return self.raw({"status": TaskStatusConst.ONGOING})

    def completed(self):
        return self.raw({"status": TaskStatusConst.COMPLETED})

    def aborted(self):
        return self.raw({"status": TaskStatusConst.ABORTED})

    def failed(self):
        return self.raw({"status": TaskStatusConst.FAILED})

    def canceled(self):
        return self.raw({"status": TaskStatusConst.CANCELED})

    def preempted(self):
        return self.raw({"status": TaskStatusConst.PREEMPTED})


TaskManager = Manager.from_queryset(TaskQuerySet)
TaskStatusManager = Manager.from_queryset(TaskStatusQuerySet)


class TaskConstraints(EmbeddedMongoModel):
    hard = fields.BooleanField(default=True)

    @classmethod
    def from_payload(cls, payload):
        document = Document.from_payload(payload)
        task_constraints = cls.from_document(document)
        return task_constraints

    def to_dict(self):
        dict_repr = self.to_son().to_dict()
        dict_repr.pop('_cls')
        return dict_repr


class TaskPlan(EmbeddedMongoModel):
    robot = fields.CharField(primary_key=True)
    actions = fields.EmbeddedDocumentListField(Action)


class Task(MongoModel):
    task_id = fields.UUIDField(primary_key=True)
    request = fields.ReferenceField(TaskRequest)
    assigned_robots = fields.ListField(blank=True)
    plan = fields.EmbeddedDocumentListField(TaskPlan, blank=True)
    constraints = fields.EmbeddedDocumentField(TaskConstraints)
    start_time = fields.DateTimeField()
    finish_time = fields.DateTimeField()

    objects = TaskManager()

    class Meta:
        archive_collection = 'task_archive'
        ignore_unknown_fields = True
        meta_model = 'task'

    def save(self):
        try:
            super().save(cascade=True)
        except ServerSelectionTimeoutError:
            logging.warning('Could not save models to MongoDB')

    @classmethod
    def create_new(cls, **kwargs):
        if 'task_id' not in kwargs.keys():
            task_id = uuid.uuid4()
            task = cls(task_id, **kwargs)
        else:
            task = cls(**kwargs)

        task.save()
        task.update_status(TaskStatusConst.UNALLOCATED)
        return task

    @classmethod
    def from_payload(cls, payload, **kwargs):
        document = Document.from_payload(payload)
        document['_id'] = document.pop('task_id')
        for key, value in kwargs.items():
            document[key] = value.from_payload(document.pop(key))
        task = cls.from_document(document)
        task.save()
        task.update_status(TaskStatusConst.UNALLOCATED)
        return task

    def to_dict(self):
        dict_repr = self.to_son().to_dict()
        dict_repr.pop('_cls')
        dict_repr["task_id"] = str(dict_repr.pop('_id'))
        dict_repr["constraints"] = self.constraints.to_dict()
        return dict_repr

    def to_msg(self):
        msg = Message.from_model(self)
        return msg

    @classmethod
    def from_request(cls, request):
        constraints = TaskConstraints(hard=request.hard_constraints)
        task = cls.create_new(request=request.request_id, constraints=constraints)
        return task

    @property
    def delayed(self):
        return self.status.delayed

    @delayed.setter
    def delayed(self, boolean):
        task_status = Task.get_task_status(self.task_id)
        task_status.delayed = boolean
        task_status.save()

    @property
    def hard_constraints(self):
        return self.constraints.hard

    @hard_constraints.setter
    def hard_constraints(self, boolean):
        self.constraints.hard = boolean
        self.save()

    def archive(self):
        with switch_collection(Task, Task.Meta.archive_collection):
            super().save()
        self.delete()

    def update_status(self, status):
        try:
            task_status = Task.get_task_status(self.task_id)
            task_status.status = status
        except DoesNotExist:
            task_status = TaskStatus(task=self.task_id, status=status)
        task_status.save()
        if status in [TaskStatusConst.COMPLETED, TaskStatusConst.CANCELED, TaskStatusConst.ABORTED]:
            task_status.archive()
            self.archive()

    def assign_robots(self, robot_ids):
        self.assigned_robots = robot_ids
        self.save()

    def update_plan(self, robot_id, task_plan):
        # This might not work for tasks with multiple robots
        for robot in robot_id:
            task_plan.robot = robot
            self.plan.append(task_plan)
        self.update_status(TaskStatusConst.PLANNED)
        self.save()

    def update_schedule(self, schedule):
        self.start_time = schedule['start_time']
        self.finish_time = schedule['finish_time']
        self.save()

    def is_executable(self):
        current_time = TimeStamp()
        start_time = TimeStamp.from_datetime(self.start_time)

        if start_time < current_time:
            return True
        else:
            return False

    @property
    def meta_model(self):
        return self.Meta.meta_model

    @property
    def status(self):
        return TaskStatus.objects.get({"_id": self.task_id})

    @classmethod
    def get_task(cls, task_id):
        return cls.objects.get_task(task_id)


    @staticmethod
    def get_task_status(task_id):
        return TaskStatus.objects.get({'_id': task_id})


    @staticmethod
    def get_tasks_by_status(status):
        return [status.task for status in TaskStatus.objects.by_status(status)]


    @classmethod
    def get_tasks_by_robot(cls, robot_id):
        return [task for task in cls.objects.all() if robot_id in task.assigned_robots]


    @classmethod
    def get_tasks(cls, robot_id=None, status=None):
        if status:
            tasks = cls.get_tasks_by_status(status)
        else:
            tasks = cls.objects.all()

        tasks_by_robot = [task for task in tasks if robot_id in task.assigned_robots]

        return tasks_by_robot

    def update_progress(self, action_id, action_status, **kwargs):
        status = TaskStatus.objects.get({"_id": self.task_id})
        status.update_progress(action_id, action_status, **kwargs)


class TimepointConstraint(EmbeddedMongoModel):
    earliest_time = fields.DateTimeField()
    latest_time = fields.DateTimeField()

    def __str__(self):
        to_print = ""
        to_print += "[{}, {}]".format(self.earliest_time.isoformat(), self.latest_time.isoformat())
        return to_print

    @classmethod
    def from_payload(cls, payload):
        document = Document.from_payload(payload)
        document["earliest_time"] = dateutil.parser.parse(document.pop("earliest_time"))
        document["latest_time"] = dateutil.parser.parse(document.pop("latest_time"))
        return cls.from_document(document)

    def to_dict(self):
        dict_repr = self.to_son().to_dict()
        dict_repr.pop('_cls')
        dict_repr["earliest_time"] = self.earliest_time.isoformat()
        dict_repr["latest_time"] = self.latest_time.isoformat()
        return dict_repr

    def update(self, earliest_time, latest_time):
        self.earliest_time = earliest_time
        self.latest_time = latest_time


class InterTimepointConstraint(EmbeddedMongoModel):
    mean = fields.FloatField()
    variance = fields.FloatField()

    @property
    def standard_dev(self):
        return round(self.variance ** 0.5, 3)

    def __str__(self):
        to_print = ""
        to_print += "N({}, {})".format(self.mean, self.standard_dev)
        return to_print

    @classmethod
    def from_payload(cls, payload):
        document = Document.from_payload(payload)
        return cls.from_document(document)

    def to_dict(self):
        dict_repr = self.to_son().to_dict()
        dict_repr.pop('_cls')
        return dict_repr

    def update(self, mean, variance):
        self.mean = mean
        self.variance = variance


class TransportationTemporalConstraints(EmbeddedMongoModel):
    pickup = fields.EmbeddedDocumentField(TimepointConstraint)
    duration = fields.EmbeddedDocumentField(InterTimepointConstraint)

    @classmethod
    def from_payload(cls, payload):
        document = Document.from_payload(payload)
        document['pickup'] = TimepointConstraint.from_payload(document.get('pickup'))
        document['duration'] = InterTimepointConstraint.from_payload(document.get('duration'))
        temporal_constraints = cls.from_document(document)
        return temporal_constraints

    def to_dict(self):
        dict_repr = self.to_son().to_dict()
        dict_repr.pop('_cls')
        dict_repr['pickup'] = self.pickup.to_dict()
        dict_repr['duration'] = self.duration.to_dict()
        return dict_repr


class TransportationTaskConstraints(TaskConstraints):
    temporal = fields.EmbeddedDocumentField(TransportationTemporalConstraints)

    @classmethod
    def from_payload(cls, payload):
        document = Document.from_payload(payload)
        document["temporal"] = TransportationTemporalConstraints.from_payload(document.pop("temporal"))
        task_constraints = cls.from_document(document)
        return task_constraints

    def to_dict(self):
        dict_repr = super().to_dict()
        dict_repr['temporal'] = self.temporal.to_dict()
        return dict_repr


class TransportationTask(Task):
    constraints = fields.EmbeddedDocumentField(TransportationTaskConstraints)

    objects = TaskManager()

    @classmethod
    def create_new(cls, **kwargs):
        task = super().create_new(**kwargs)
        if task.constraints is None:
            pickup = TimepointConstraint(earliest_time=datetime.now(),
                                         latest_time=datetime.now() + timedelta(minutes=1))
            temporal = TransportationTemporalConstraints(pickup=pickup, duration=InterTimepointConstraint())
            task.constraints = TransportationTaskConstraints(temporal=temporal)
        task.save()
        return task

    @classmethod
    def from_request(cls, request):
        pickup = TimepointConstraint(earliest_time=request.earliest_pickup_time, latest_time=request.latest_pickup_time)
        temporal = TransportationTemporalConstraints(pickup=pickup, duration=InterTimepointConstraint())
        constraints = TransportationTaskConstraints(hard=request.hard_constraints, temporal=temporal)
        task = cls.create_new(request=request.request_id, constraints=constraints)
        return task

    def archive(self):
        with switch_collection(TransportationTask, Task.Meta.archive_collection):
            super().save()
        self.delete()

    @property
    def duration(self):
        return self.constraints.temporal.duration

    def update_duration(self, mean, variance):
        self.duration.update(mean, variance)
        self.save()

    @property
    def pickup_constraint(self):
        return self.constraints.temporal.pickup

    def update_pickup_constraint(self, earliest_time, latest_time):
        self.pickup_constraint.update(earliest_time, latest_time)
        self.save()

    @classmethod
    def get_earliest_task(cls, tasks=None):
        if tasks is None:
            tasks = [task for task in cls.objects.all()]
        earliest_time = datetime.max
        earliest_task = None
        for task in tasks:
            if task.pickup_constraint.earliest_time < earliest_time:
                earliest_time = task.pickup_constraint.earliest_time
                earliest_task = task
        return earliest_task


class TaskProgress(EmbeddedMongoModel):

    current_action = fields.ReferenceField(Action)
    actions = fields.EmbeddedDocumentListField(ActionProgress)

    class Meta:
        ignore_unknown_fields = True

    def update(self, action_id, action_status, **kwargs):
        if action_status == ActionStatus.COMPLETED:
            self.current_action = self._get_next_action(action_id).action.action_id \
                if self._get_next_action(action_id) is not None else self.current_action

        self.update_action_progress(action_id, action_status, **kwargs)

    def update_action_progress(self, action_id, action_status, **kwargs):
        idx = self._get_action_index(action_id)
        self.actions.pop(idx)
        action_progress = ActionProgress(action_id, action_status, **kwargs)
        self.actions.insert(idx, action_progress)

    def complete(self):
        self.current_action = None
        self.save(cascade=True)

    def get_action(self, action_id):
        idx = self._get_action_index(action_id)
        return self.actions[idx]

    def _get_action_index(self, action_id):
        if isinstance(action_id, str):
            action_id_ = uuid.UUID(action_id)
        else:
            action_id_ = action_id

        idx = None
        for a in self.actions:
            if a.action.action_id == action_id_:
                idx = self.actions.index(a)

        return idx

    def _get_next_action(self, action_id):
        idx = self._get_action_index(action_id)
        try:
            return self.actions[idx + 1]
        except IndexError:
            # The last action has no next action
            return None

    def initialize(self, action_id, task_plan):
        self.current_action = action_id
        for action in task_plan[0].actions:
            self.actions.append(ActionProgress(action.action_id))


class TaskStatus(MongoModel):
    task = fields.ReferenceField(Task, primary_key=True, required=True)
    status = fields.IntegerField(default=TaskStatusConst.UNALLOCATED)
    delayed = fields.BooleanField(default=False)
    progress = fields.EmbeddedDocumentField(TaskProgress)

    objects = TaskStatusManager()

    class Meta:
        archive_collection = 'task_status_archive'
        ignore_unknown_fields = True

    def archive(self):
        with switch_collection(TaskStatus, TaskStatus.Meta.archive_collection):
            super().save()
        self.delete()

    def update_progress(self, action_id, action_status, **kwargs):
        self.refresh_from_db()
        if not self.progress:
            self.progress = TaskProgress()
            self.progress.initialize(action_id, self.task.plan)
            self.save()
        self.progress.update(action_id, action_status, **kwargs)
        self.save(cascade=True)
