from pymodm import EmbeddedMongoModel, fields


class Position(EmbeddedMongoModel):

    x = fields.FloatField()
    y = fields.FloatField()
    theta = fields.FloatField()

    class Meta:
        ignore_unknown_fields = True

    def update_2d_pose(self, x, y, theta):
        self.x = x
        self.y = y
        self.theta = theta
