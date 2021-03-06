import os.path

user = 'www-data'
group = 'www-data'

debug = 'false'
daemon = 'true'

bind = 'unix:/tmp/rpclient.gunicorn.sock'

_LOG_PATH = '/var/log'
errorlog = os.path.join(_LOG_PATH, 'restpipe.log')
loglevel = 'info'
worker_class = 'gevent'
