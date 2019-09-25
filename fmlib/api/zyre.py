import logging

from ropod.pyre_communicator.base_class import RopodPyre


class ZyreInterface(RopodPyre):
    def __init__(self, zyre_node, logger_name='fms.api.zyre', **kwargs):
        super().__init__(zyre_node, acknowledge=kwargs.get('acknowledge', False))
        self.logger = logging.getLogger(logger_name)
        self.callback_dict = dict()
        self.debug_messages = kwargs.get('debug_messages', list())
        self.publish_dict = kwargs.get('publish', dict())
        self.logger.debug(self.publish_dict)

    def register_callback(self, function, msg_type, **kwargs):
        self.logger.debug("Adding callback function %s for message type %s", function.__name__,
                          msg_type)
        self.__dict__[function.__name__] = function
        self.callback_dict[msg_type] = function.__name__

    def receive_msg_cb(self, msg_content):
        dict_msg = self.convert_zyre_msg_to_dict(msg_content)
        if dict_msg is None:
            self.logger.warning("Message is not a dictionary")
            return

        message_type = dict_msg['header']['type']
        # Ignore messages not declared in our message type
        if message_type not in self.message_types:
            return
        elif message_type in self.debug_messages:
            payload = dict_msg.get('payload')
            self.logger.debug("Received %s message, with payload %s", message_type, payload)

        callback = None

        try:
            callback = self.callback_dict.get(message_type, None)
            if callback is None:
                raise AttributeError
        except AttributeError:
            self.logger.error("No callback function found for %s messages. Callback dictionary: %s",
                              message_type, self.callback_dict)

        try:
            if callback:
                getattr(self, callback)(dict_msg)
        except AttributeError:
            self.logger.error("Could not execute callback %s ", callback, exc_info=True)

    def run(self):
        if self.acknowledge:
            self.resend_message_cb()
