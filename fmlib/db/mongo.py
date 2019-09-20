import logging

from pymodm import connection
from pymodm import connect
from pymongo.errors import ServerSelectionTimeoutError


class MongoStore:

    def __init__(self, db_name, port=27017, **kwargs):
        self.logger = logging.getLogger(__name__)
        self.db_name = db_name
        self.port = port
        self.ip = kwargs.get('ip', 'localhost')
        self._connected = False
        self._connection_timeout = kwargs.get('connectTimeoutMS', 30) * 1000

        self.connect()

    def connect(self):
        if self._connected:
            return

        connection_str = "mongodb://%s:%s/%s" % (self.ip, self.port, self.db_name)

        try:
            # Default timeout is 30s
            connect(connection_str, alias="default", serverSelectionTimeoutMS=self._connection_timeout)
            self._connected = True
        except ServerSelectionTimeoutError as err:
            self.logger.critical("Cannot connect to MongoDB", exc_info=True)
            self._connected = False
            return

        self.logger.info("Connected to %s on port %s", self.db_name, self.port)

    @property
    def connected(self):
        if not self._connected:
            self.connect()

        return self._connected


class MongoStoreInterface:

    def __init__(self, mongo_store=None):
        self.logger = logging.getLogger(__name__)
        self._store = mongo_store

    def save(self, model):
        if self._store.connected:
            try:
                model.save()
            except ServerSelectionTimeoutError as err:
                self.logger.error(err)

    def archive(self, model):
        if self._store.connected:
            try:
                model.archive()
            except ServerSelectionTimeoutError as err:
                self.logger.error(err)

    def update(self, model, **kwargs):
        if self._store.connected:
            try:
                model.update(**kwargs)
            except ServerSelectionTimeoutError as err:
                self.logger.error(err)

    def clean(self):
        if self._store.connected:
            try:
                connection._get_db(alias="default").client.drop_database(self._store.db_name)
            except ServerSelectionTimeoutError as err:
                self.logger.error(err)


class MongoStoreBuilder:

    def __init__(self):
        self._instance = None

    def __call__(self, db_name, port, **_):
        if not self._instance:
            store = MongoStore(db_name, port)
            self._instance = MongoStoreInterface(store)
        return self._instance


Store = MongoStoreBuilder()
