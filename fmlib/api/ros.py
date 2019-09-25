import logging
from importlib import import_module

import rospy

from rospy_message_converter import message_converter

from ropod_ros_msgs.msg import Task, TaskRequest


class ROSInterface:
    """
    ROSInterface.
    """

    def __init__(self, **kwargs):
        super(ROSInterface, self).__init__()
        rospy.init_node('fms_ros_api', anonymous=False, disable_signals=True)
        self.logger = logging.getLogger('fms.api.ros')
        self._publisher_dict = dict()

        rospy.on_shutdown(self.shutdown)
        self._configure(**kwargs)
        self.logger.info("Initialized fleet management ROS interface")

    def _configure(self, **kwargs):
        self.logger.error(kwargs)
        for publisher in kwargs.get('publishers', list()):
            pub = self.add_publisher(**publisher)
            self._publisher_dict[publisher.get('topic')] = pub

        rospy.logerr('Configured publishers...')

        for subscriber in kwargs.get('subscribers', list()):
            self.add_subscriber(**subscriber)

    def _get_ros_msg(self, msg_type, msg_module):
        msg_module = import_module(msg_module)
        return getattr(msg_module, msg_type)

    def add_publisher(self, topic, msg_type, msg_module):
        msg = self._get_ros_msg(msg_type, msg_module)
        return rospy.Publisher(topic, msg, queue_size=50)

    def add_subscriber(self, topic, msg_type, msg_module, callback):
        msg = self._get_ros_msg(msg_type, msg_module)
        callback = getattr(self, callback)
        return rospy.Subscriber(topic, msg, callback)

    def task_cb(self, msg):
        msg_dict = message_converter.convert_ros_message_to_dictionary(msg)
        msg_ros = message_converter.convert_dictionary_to_ros_message('ropod_ros_msgs/TaskRequest', msg_dict)
        task = Task()
        self._publisher_dict['/fms/task'].publish(task)

    def start(self):
        rospy.loginfo("Started ROS interface of rospy")
        self.logger.error("Started ROS interface!")

    def shutdown(self):
        rospy.loginfo("Shutting down rospy")
        self.logger.warning("Shutting down ROS interface")

    def run(self):
        if not rospy.is_shutdown():
            try:
                #self.logger.info('Running')
                pass
            except (rospy.ROSInterruptException, KeyboardInterrupt):
                rospy.logerr("Terminating node")
                self.logger.error('Terminating ROS interface')


