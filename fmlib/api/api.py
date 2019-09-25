"""This module contains the API class that allows components to receive and
send messages through the network using a variety of middlewares
"""

import logging

from fmlib.api.rest.interface import RESTInterface
from fmlib.api.ros import ROSInterface
from fmlib.api.zyre import ZyreInterface
from fmlib.utils.messages import MessageFactory


class API:
    """API object serves as a facade to different middlewares

        Args:
            middleware: a list of middleware to configure.
            The keyword arguments should containing the desired configuration
            matching the middleware listed

        Attributes:
            publish_dict: A dictionary that maps
            middleware_collection: A list of supported middlewares obtained from the config file
            config_params: A dictionary containing the parameters loaded from the config file
            _mf: An object of type MessageFactory to create message templates
    """

    def __init__(self, middleware, **kwargs):
        self.logger = logging.getLogger(__name__)

        self.publish_dict = dict()
        self.interfaces = list()
        self.config_params = dict()
        self.middleware_collection = middleware
        self._configure(kwargs)
        self._mf = MessageFactory()

        self.logger.info("Initialized API")

    def publish(self, msg, **kwargs):
        """Publishes a message using the configured functions per middleware

        Args:
            msg: a JSON message
            **kwargs: keyword arguments to be passed to the configured functions
        """
        try:
            msg_type = msg.get('header').get('type')
        except AttributeError:
            self.logger.error("Could not get message type from message: %s", msg, exc_info=True)
            return

        self.logger.debug("Publishing message of type %s", msg_type)

        try:
            method = self.publish_dict.get(msg_type.lower()).get('method')
        except ValueError:
            self.logger.error("No method defined for message %", msg_type)
            return

        for option in self.middleware_collection:
            self.logger.debug('Using method %s to publish message using %s', method, option)
            getattr(self.__dict__[option], method)(msg, **kwargs)

    def _configure(self, config_params):
        for option in self.middleware_collection:
            config = config_params.get(option, None)
            self.config_params[option] = config
            if config is None:
                self.logger.warning("Option %s present, but no configuration was found", option)
                self.__dict__[option] = None
                continue

            self.logger.debug("Configuring %s API", option)
            interface = None
            if option == 'zyre':
                interface = API.get_zyre_api(config)
            elif option == 'ros':
                interface = API.get_ros_api(config)
            elif option == 'rest':
                interface = API.get_rest_api(config)

            self.__dict__[option] = interface
            self.interfaces.append(interface)

        self.publish_dict.update(config_params.get('zyre').get('publish'))
        self.logger.debug("Publish dictionary: %s", self.publish_dict)

    @staticmethod
    def get_zyre_api(zyre_config):
        """Create an object of type ZyreInterface

        Args:
            zyre_config: A dictionary containing the API configuration

        Returns:
            A configured ZyreInterface object

        """
        zyre_api = ZyreInterface(**zyre_config)
        return zyre_api

    @staticmethod
    def get_ros_api(ros_config):
        """Create an object of type ROSInterface

        Args:
            ros_config: A dictionary containing the API configuration

        Returns:
            A configured ROSInterface object
        """
        return ROSInterface(**ros_config)

    @staticmethod
    def get_rest_api(rest_config):
        """Create an object of type RESTInterface

        Args:
            rest_config: A dictionary containing the API configuration

        Returns:
            A configured RESTInterface object

        """
        return RESTInterface(**rest_config)

    def register_callbacks(self, obj, callback_config=None):
        for option in self.middleware_collection:
            if callback_config is None:
                option_config = self.config_params.get(option, None)
            else:
                option_config = callback_config.get(option, None)

            if option_config is None:
                logging.warning("Option %s has no configuration", option)
                continue

            callbacks = option_config.get('callbacks', list())
            for callback in callbacks:
                component = callback.get('component', None)
                try:
                    function = _get_callback_function(obj, component)
                except AttributeError as err:
                    self.logger.error("%s. Skipping %s callback.", err, component)
                    continue
                self.__register_callback(option, function, **callback)

    def __register_callback(self, middleware, function, **kwargs):
        """Adds a callback function to the right middleware

        Args:
            middleware: a string specifying which middleware to use
            function: an instance of the function to call
            **kwargs:

        """
        self.logger.info("Adding %s callback to %s", function, middleware)
        getattr(self, middleware).register_callback(function, **kwargs)

    def start(self):
        """Start the API components
        """
        for interface in self.interfaces:
            interface.start()

    def shutdown(self):
        """Shutdown all API components
        """
        for interface in self.interfaces:
            interface.shutdown()

    def run(self):
        """Execute the API's specific methods
        """
        for interface in self.interfaces:
            interface.run()

    def create_message(self, model):
        return self._mf.create_message(model)


def _get_callback_function(obj, component):
    objects = component.split('.')
    child = objects.pop(0)
    if child:
        parent = getattr(obj, child)
    else:
        parent = obj
    while objects:
        child = objects.pop(0)
        parent = getattr(parent, child)

    return parent


class InterfaceBuilder:
    pass
