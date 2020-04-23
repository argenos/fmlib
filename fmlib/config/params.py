from fmlib.utils.utils import load_file_from_module, load_yaml, load_yaml_config_file


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
        config = load_yaml(config_file)
        return cls(config)

    @classmethod
    def from_file(cls, config_file):
        config = load_yaml_config_file(config_file)
        return cls(config)
