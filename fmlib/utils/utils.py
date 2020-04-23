import yaml
from importlib_resources import open_text


def load_file_from_module(module, file_name):
    config_file = open_text(module, file_name)
    return config_file


# YAML config files
def load_yaml(yaml_file):
    data = yaml.safe_load(yaml_file)
    return data


def load_yaml_config_file(file_name):
    with open(file_name, 'r') as file_handle:
        config = load_yaml(file_handle)
    return config
