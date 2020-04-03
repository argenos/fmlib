"""This module provides classes for manipulate messages

Inspired by https://realpython.com/inheritance-composition-python/
"""

import json
import logging

import inflection
from ropod.utils.timestamp import TimeStamp
from ropod.utils.uuid import generate_uuid


def format_msg(msg_dict):
    def _format_msg_keys(value):
        return {inflection.camelize(prop, False): format_msg(value)
                for prop, value in value.items()}

    if isinstance(msg_dict, dict):
        return _format_msg_keys(msg_dict)
    else:
        return msg_dict


def format_document(doc_dict):
    def _format_doc_keys(doc):
        return {inflection.underscore(prop): format_document(value)
                for prop, value in doc.items()}

    if isinstance(doc_dict, dict):
        return _format_doc_keys(doc_dict)
    else:
        return doc_dict


class Header:

    def __new__(cls, message_type, meta_model=None, **kwargs):

        recipients = kwargs.get('recipients', list())
        if recipients is not None and not isinstance(recipients, list):
            raise Exception("Recipients must be a list of strings")

        return {'type': message_type,
                'metamodel': meta_model,
                'msgId': str(generate_uuid()),
                'timestamp': TimeStamp().to_str(),
                'receiverIds': recipients}


class Payload:

    def __new__(cls, model, **kwargs):
        """Creates a python dictionary from a fmlib model

        The generated payload doesn't include a meta model yet.

        Args:
            model: An fmlib model

        Returns:
            payload (dict): A python dictionary
        """
        payload = format_msg(model.to_dict())
        return payload


class Message(dict):

    def __init__(self, payload, header=None, **kwargs):
        super().__init__()

        if header:
            self.update(header=header)
        else:
            msg_type = kwargs.get('message_type', '')
            self.update(header=Header(msg_type))

        self.update(payload=payload)

    def __str__(self):
        return json.dumps(self, indent=2)

    @property
    def type(self):
        if self.get('header'):
            return self.get('header').get('type')
        else:
            return None

    @property
    def payload(self):
        return self.get('payload')

    @property
    def header(self):
        return self.get('header')

    @property
    def timestamp(self):
        return self.get('header').get('timestamp')

    @classmethod
    def from_model(cls, model, **kwargs):
        meta_model_template = kwargs.get('template', '%s')
        mf = MessageFactory(meta_model_template)
        return mf.create_message(model)

    def refresh(self):
        """Update the header with new values
        """
        self['header']['timestamp'] = TimeStamp().to_str()
        self['header']['msgId'] = str(generate_uuid())


class MessageFactory:

    def __init__(self, meta_model_prefix=None):
        self.logger = logging.getLogger(__name__)
        if meta_model_prefix is None:
            self.meta_model_template = "%s-schema.json"
        else:
            self.meta_model_template = meta_model_prefix + "-%s-schema.json"
        self.logger.debug("Initialized with meta model prefix: %s", meta_model_prefix)

    def create_payload(self, model):
        """Creates a python dictionary from a fmlib model

        Args:
            model: An fmlib model

        Returns:
            payload (dict): A python dictionary in a payload format
        """
        payload = Payload(model)
        meta_model = self.meta_model_template % model.meta_model
        payload.update(metamodel=meta_model)
        return payload

    def create_header(self, message_type, **kwargs):
        meta_model = self.meta_model_template % 'msg'
        return Header(message_type.upper(), meta_model, **kwargs)

    def create_message(self, model, **kwargs):
        self.logger.debug("Creating message for model %s", model)
        payload = self.create_payload(model)
        header = self.create_header(model.meta_model, **kwargs)
        msg = Message(payload, header)
        return msg


class Document(dict):

    def __init__(self, payload):
        super().__init__()
        self.update(**payload)

    @classmethod
    def from_payload(cls, payload):
        return cls(format_document(payload))
