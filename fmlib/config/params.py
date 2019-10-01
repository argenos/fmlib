import yaml
from fmlib.utils.utils import load_file_from_module


class ConfigParams(dict):

    default_config_module = 'fmlib.config.default'

    def __init__(self, config=None):
        super().__init__()

        if config is None:
            config = dict()
        self.update(**config)

    @classmethod
    def component(cls, component, config_file=None):
        config = cls(config_file)
        return config.pop(component)

    @classmethod
    def default(cls):
        config_file = load_file_from_module(cls.default_config_module, 'config.yaml')
        config = _load_yaml(config_file)
        return cls(config)

    @classmethod
    def from_file(cls, config_file):
        config = _load_yaml_config_file(config_file)
        return cls(config)


# YAML config files
def _load_yaml(yaml_file):
    data = yaml.safe_load(yaml_file)
    return data


def _load_yaml_config_file(file_name):
    with open(file_name, 'r') as file_handle:
        config = _load_yaml(file_handle)
    return config

