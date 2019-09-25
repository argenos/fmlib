import falcon
import logging
import threading

from importlib import import_module
from wsgiref import simple_server

import gunicorn.app.base
from gunicorn.six import iteritems


class GunicornServer(gunicorn.app.base.BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super(GunicornServer, self).__init__()
        self.logger = logging.getLogger('fms.api.rest.gunicorn')

    def load_config(self):
        config = dict([(key, value) for key, value in iteritems(self.options)
                       if key in self.cfg.settings and value is not None])
        for key, value in iteritems(config):
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

    def init(self, **kwargs):
        self.logger.info("Initialised REST interface")

    def start(self):
        self.run()


class RESTInterface(object):
    def __init__(self, server, **kwargs):
        self.server_config = server
        self.ip = server.get('ip', '127.0.0.1')
        self.port = server.get('port', 8080)
        self.logger = logging.getLogger('fms.api.rest')
        self.app = falcon.API()
        self.server = simple_server.make_server(self.ip, self.port, self.app)
        self.threads = list()
        self._configure(**kwargs)
        self.logger.info("Initialized REST interface")

    def _configure(self, **kwargs):
        routes = kwargs.get('routes', list())
        for route in routes:
            path = route.get('path')
            resource_config = route.get('resource')
            resource_module = import_module(resource_config.get('module'))
            resource_class = getattr(resource_module, resource_config.get('class'))
            self.app.add_route(path, resource_class())

    def add_route(self, route, resource):
        self.app.add_route(route, resource)

    def start(self):
        x = threading.Thread(target=self.server.serve_forever)
        self.threads.append(x)
        try:
            x.start()
        except (KeyboardInterrupt, SystemExit):
            self.logger.info('Terminating REST interface')

    def shutdown(self):
        self.server.shutdown()
        self.threads[0].join()

    def run(self):
        pass

    def register_callback(self, function, **kwargs):
        pass


if __name__ == '__main__':
    # from fleet_management.config.loader import Config
    #config = Config(initialize=False)
    # config.configure_logger()
    api = RESTInterface(ip='127.0.0.1', port=8080)
    api.start()
