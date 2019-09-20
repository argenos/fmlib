import uuid

from fmlib.models.tasks import Task, TaskStatus


def get_task(task_id):
    return Task.objects.get_task(task_id)


def get_task_status(task_id):
    return TaskStatus.get({'_id': uuid.UUID(task_id)})


def get_tasks_by_status(status):
    return [status.task for status in TaskStatus.objects.by_status(status)]


def get_tasks_by_robot(robot_id):
    return [task for task in Task.objects.all() if robot_id in task.assigned_robots]


def get_tasks(robot_id=None, status=None):
    if status:
        tasks = get_tasks_by_status(status)
    else:
        tasks = Task.objects.all()

    tasks_by_robot = [task for task in tasks if robot_id in task.assigned_robots]

    return tasks_by_robot
