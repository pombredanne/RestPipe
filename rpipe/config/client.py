import os
import os.path
import sys

USER_CONFIG_MODULE_NAME = os.environ.get('RP_CLIENT_USER_CONFIG_MODULE', '')

TARGET_HOSTNAME = os.environ.get('RP_CLIENT_TARGET_HOSTNAME', 'localhost')
TARGET_PORT = int(os.environ.get('RP_CLIENT_TARGET_PORT', '1234'))

_CERT_PATH = os.environ.get('RP_CLIENT_CERT_PATH', '/var/lib/restpipe')

if os.path.exists(_CERT_PATH) is False:
    os.mkdir(_CERT_PATH)

_KEY_FILENAME = os.environ.get('RP_CLIENT_KEY_FILENAME', 'restpipe.client.key.pem')
_CRT_FILENAME = os.environ.get('RP_CLIENT_CRT_FILENAME', 'restpipe.client.crt.pem')

KEY_FILEPATH = os.path.join(_CERT_PATH, _KEY_FILENAME)
CRT_FILEPATH = os.path.join(_CERT_PATH, _CRT_FILENAME)

DEFAULT_READ_CHUNK_LENGTH = 1024
HEARTBEAT_INTERVAL_S = 5
MAX_CONNECT_ATTEMPTS = 0
RECONNECT_DELAY_S = 5

EVENT_HANDLER_FQ_CLASS = \
    os.environ.get(
        'RP_EVENT_HANDLER_FQ_CLASS',
        'rpipe.client.connection.TestClientEventHandler')

MINIMAL_CONNECTION_FAIL_REATTEMPT_WAIT_TIME_S = 2

# Install attributes on this module from the optional user-config.
if USER_CONFIG_MODULE_NAME != '':
    _MODULE = sys.modules[__name__]

    _UM = __import__(USER_CONFIG_MODULE_NAME)

    for key in dir(_UM):
        if key[0] != '_':
            setattr(_MODULE, key, getattr(_UM, key))
