import logging
import uuid

from fmlib.models.actions import Action, ActionProgress
from fmlib.models.requests import TaskRequest
from fmlib.utils.messages import Document
from fmlib.utils.messages import Message
from pymodm import EmbeddedMongoModel, fields, MongoModel
from pymodm.context_managers import switch_collection
from pymodm.manager import Manager
from pymodm.queryset import QuerySet
from pymongo.errors import ServerSelectionTimeoutError
from ropod.structs.status import ActionStatus, TaskStatus as TaskStatusConst
from ropod.utils.timestamp import TimeStamp
from pymodm.errors import DoesNotExist


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


class TimepointConstraints(EmbeddedMongoModel):
    earliest_time = fields.DateTimeField()
    latest_time = fields.DateTimeField()

    @staticmethod
    def relative_to_ztp(timepoint, ztp, resolution="minutes"):
        """ Returns the timepoint constraints relative to a ZTP (zero timepoint)

        Args:
            timepoint (TimepointConstraints): timepoint
            ztp (TimeStamp): Zero Time Point. Origin time to which the timepoint will be referenced to
            resolution (str): Resolution of the difference between the timepoint constraints and the ztp

        Return: r_earliest_time (float): earliest time relative to the ztp
                r_latest_time (float): latest time relative to the ztp
        """

        r_earliest_time = TimeStamp.from_datetime(timepoint.earliest_time).get_difference(ztp, resolution)
        r_latest_time = TimeStamp.from_datetime(timepoint.latest_time).get_difference(ztp, resolution)

        return r_earliest_time, r_latest_time

    @classmethod
    def from_payload(cls, payload):
        document = Document.from_payload(payload)
        timepoint_constraints = TimepointConstraints.from_document(document)
        return timepoint_constraints

    def to_dict(self):
        dict_repr = self.to_son().to_dict()
        dict_repr.pop('_cls')
        dict_repr["earliest_time"] = self.earliest_time.isoformat()
        dict_repr["latest_time"] = self.latest_time.isoformat()
        return dict_repr


class TaskConstraints(EmbeddedMongoModel):
    hard = fields.BooleanField(default=True)
    timepoint_constraints = fields.EmbeddedDocumentListField(TimepointConstraints)

    @classmethod
    def from_payload(cls, payload):
        document = Document.from_payload(payload)
        timepoint_constraints = [TimepointConstraints.from_payload(timepoint_constraint)
                                 for timepoint_constraint in document.get("timepoint_constraints")]
        document["timepoint_constraints"] = timepoint_constraints
        task_constraints = TaskConstraints.from_document(document)
        return task_constraints

    def to_dict(self):
        dict_repr = self.to_son().to_dict()
        dict_repr.pop('_cls')
        timepoint_constraints = [timepoint_constraint.to_dict() for timepoint_constraint in self.timepoint_constraints]
        dict_repr["timepoint_constraints"] = timepoint_constraints
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
    duration = fields.FloatField()
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
    def from_payload(cls, payload):
        document = Document.from_payload(payload)
        document['_id'] = document.pop('task_id')
        task = Task.from_document(document)
        task.save()
        task.update_status(TaskStatusConst.UNALLOCATED)
        return task

    def to_dict(self):
        dict_repr = self.to_son().to_dict()
        dict_repr.pop('_cls')
        dict_repr["task_id"] = str(dict_repr.pop('_id'))
        return dict_repr

    def to_msg(self):
        msg = Message.from_model(self)
        return msg

    @classmethod
    def from_request(cls, request):
        constraints = TaskConstraints(hard=request.hard_constraints)
        task = cls.create_new(request=request.request_id, constraints=constraints)
        return task

    def update_duration(self, duration):
        self.duration = duration
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

    def update_constraints(self, constraints):
        pass

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

    @staticmethod
    def get_task(task_id):
        return Task.objects.get_task(task_id)


    @staticmethod
    def get_task_status(task_id):
        return TaskStatus.objects.get({'_id': task_id})


    @staticmethod
    def get_tasks_by_status(status):
        return [status.task for status in TaskStatus.objects.by_status(status)]


    @staticmethod
    def get_tasks_by_robot(robot_id):
        return [task for task in Task.objects.all() if robot_id in task.assigned_robots]


    @staticmethod
    def get_tasks(robot_id=None, status=None):
        if status:
            tasks = Task.get_tasks_by_status(status)
        else:
            tasks = Task.objects.all()

        tasks_by_robot = [task for task in tasks if robot_id in task.assigned_robots]

        return tasks_by_robot

    def update_progress(self, action_id, action_status, **kwargs):
        status = TaskStatus.objects.get({"_id": self.task_id})
        status.update_progress(action_id, action_status, **kwargs)


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
        action_progress = ActionProgress(action_id, action_status)
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
