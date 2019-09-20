from pymodm import MongoModel, fields


class User(MongoModel):

    user_id = fields.CharField(primary_key=True)
