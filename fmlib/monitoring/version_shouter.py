import os

from fmlib.api.zyre import ZyreInterface
from fmlib.utils.messages import Header
from wstool.multiproject_cmd import cmd_info, get_config


class VersionShouter:

    def __init__(self, base_path, config_filename, robot_id=None):
        zyre_config = {
            'node_name': 'version_shouter',
            'groups': ['ROPOD'],
            'message_types': []
        }

        self.shouter = ZyreInterface(zyre_config, logger_name='fms.robot.version_shouter')
        self.config = get_config(base_path, config_filename=base_path + config_filename)

        if robot_id is None:
            self.robot_id = os.environ.get('ROBOT_ID', 'ropod_001')
        else:
            self.robot_id = robot_id

    def run(self):
        self.shouter.start()
        x = cmd_info(self.config)
        msg = {'header': Header('ROBOT-VERSION'),
               'payload': {
                   'softwareVersion': x,
                   'robotId': self.robot_id
               }
               }
        self.shouter.shout(msg, groups=['ROPOD'])
        self.shouter.stop()


if __name__ == '__main__':
    base_path_ = '/absolute/path/to/workspace/src'
    config_filename_ = '.rosinstall'

    shouter = VersionShouter(base_path_, config_filename_)
    shouter.run()
