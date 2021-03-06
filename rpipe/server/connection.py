#!/usr/bin/env python2.7

import logging
import os.path
import time
import socket

import gevent
import gevent.server
import gevent.ssl

import rpipe.config.server
import rpipe.server.exceptions
import rpipe.utility
import rpipe.protocol
import rpipe.connection
import rpipe.request_server
import rpipe.message_loop

_logger = logging.getLogger(__name__)


class ServerEventHandler(object):
    pass


class TestServerEventHandler(ServerEventHandler):
    def get_time(self, ctx, post_data):
        _logger.info("TEST: get_time()")
        return { 'time_from_server': time.time() }

    def get_cat(self, ctx, post_data, x, y):
        _logger.info("TEST: get_cat()")
        return { 'result_from_server': str(x) + str(y) }


class _ConnectionCatalog(object):
    """Keep track of connections and their IPs. This is the principle reason 
    that no two clients can connect from the same host.
    """

    def __init__(self):
        self.__connections = {}

    def register(self, c):
# TODO(dustin): Connections are not being cleaned-up quick enough, and this 
#               presents reliability problems in multiple different ways.
        if c in self.__connections:
            raise ValueError("Can not register already-registered connection. "
                             "A previous connection from this client might "
                             "not've been deregistered [properly]: %s" % 
                             (c.ip))

        _logger.debug("Registering client: [%s]", c.ip)

        # These are actually indexed by address (so we can find it either 
        # with a conneciton object -or- an address).
        self.__connections[c] = c

    def deregister(self, c):
        if c not in self.__connections:
            raise ValueError("Can not deregister unregistered connection: %s" %
                             (c.ip))

        _logger.debug("Deregistering client: [%s]", c.ip)
        del self.__connections[c]

    def get_connection_by_ip(self, ip):
        return self.__connections[ip]

    def wait_for_connection(
            self, 
            ip, 
            timeout_s=rpipe.config.server.DEFAULT_CONNECTION_WAIT_TIMEOUT_S):
        """A convenience function to wait for a client to connect (if not 
        immediately available). This is to be used when we might need to wait 
        for a client to reconnect in order to fulfill a request.
        """

        stop_at = time.time() + timeout_s
        while time.time() <= stop_at:
            try:
                return self.__connections[ip]
            except KeyError:
                pass

            gevent.sleep(1)

        raise rpipe.server.exceptions.RpNoConnectionException(ip)


class ServerConnectionHandler(rpipe.connection.Connection):
    def handle(socket, address):
        raise NotImplementedError()


class DefaultServerConnectionHandler(ServerConnectionHandler):
    def __init__(self):
        self.__ws = None
        self.__address = None

    def __hash__(self):
        if self.ip is None:
            raise ValueError("Can not hash an unconnected connection object.")

        return hash(self.ip)

    def __eq__(self, o):
        if o is None:
            return False

        return hash(self) == hash(o)

    def handle_new_connection(self, socket, address):
        """We've received a new connection."""

        self.__ws = rpipe.protocol.SocketWrapper(socket, socket.makefile())
        self.__address = address
        self.__ctx = rpipe.message_loop.CONNECTION_CONTEXT_T(self.__address)

        get_connection_catalog().register(self)

        self.handle()

    def handle_close(self):
        _logger.info("Connection from [%s] closed.", self.__address)
        get_connection_catalog().deregister(self)

    def handle(self):
        event_handler_cls = rpipe.utility.load_cls_from_string(
                                rpipe.config.server.EVENT_HANDLER_FQ_CLASS)

        assert issubclass(event_handler_cls, ServerEventHandler) is True

        eh = event_handler_cls()
        cml = rpipe.message_loop.CommonMessageLoop(
                self.__ws, 
                eh, 
                self.__ctx, 
                watch_heartbeats=True)

        try:
            cml.handle(exit_on_unknown=True)
        finally:
            self.handle_close()

    def initiate_message(self, message_obj, **kwargs):
        # This only works because the CommonMessageLoop has already registered 
        # the other participant with the MessageExchange.
        return rpipe.message_exchange.send_and_receive(self.__address, message_obj)

    @property
    def socket(self):
        return self.__ws

    @property
    def address(self):
        return self.__address

    @property
    def ip(self):
        return self.__address[0]


class Server(rpipe.request_server.RequestServer):
    def __init__(self):
        fq_cls_name = rpipe.config.server.CONNECTION_HANDLER_FQ_CLASS

        self.__connection_handler_cls = rpipe.utility.load_cls_from_string(
                                            fq_cls_name)

        assert issubclass(self.__connection_handler_cls, ServerConnectionHandler)

    def process_requests(self):
        binding = (rpipe.config.server.BIND_IP, 
                   rpipe.config.server.BIND_PORT)

        _logger.info("Running server: %s", binding)

        handler = self.__connection_handler_cls()
# TODO(dustin): We need to have a watchdog process, to raise an error if nothing is connected.
# TODO(dustin): We need to debug what is dying or blocking the flow. Is it StreamServer?
        server = gevent.server.StreamServer(
                    binding, 
                    handler.handle_new_connection, 
                    cert_reqs=gevent.ssl.CERT_REQUIRED,
                    keyfile=rpipe.config.server.KEY_FILEPATH,
                    certfile=rpipe.config.server.CRT_FILEPATH,
                    ca_certs=rpipe.config.server.CA_CRT_FILEPATH)

        # Wait until termination. Generally, we should already be running in 
        # its own gthread. 
        #
        # Since there is no cleanup and everything is based on coroutines, 
        # default CTRL+BREAK and SIGTERM handling should be fine.
        server.serve_forever()

_cc = _ConnectionCatalog()

def get_connection_catalog():
    return _cc
