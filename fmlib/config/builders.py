from fmlib.db.mongo import MongoStore, MongoStoreInterface


class MongoStoreBuilder:

    def __init__(self):
        self._instance = None

    def __call__(self, db_name, port, **_):
        if not self._instance:
            store = MongoStore(db_name, port)
            self._instance = MongoStoreInterface(store)
        return self._instance


Store = MongoStoreBuilder()
