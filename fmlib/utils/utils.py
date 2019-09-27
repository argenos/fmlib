from importlib_resources import open_text


def load_file_from_module(module, file_name):
    config_file = open_text(module, file_name)
    return config_file
