import json as _json
import logging as _logging
import os as _os
import os.path as _path
import sys as _sys

import fooster.web as _web


# address to listen on
addr = ('', 8000)

# log locations
log = '/var/log/cms/cms.log'
http_log = '/var/log/cms/http.log'

# template directory to use
template = _path.dirname(__file__) + '/html'

# root directory of markdown files
root = '/var/www/cms'

# whether this website is a blog
blog = False

# datetime timezone
timezone = 'UTC'

# markdown extensions
extensions = ['sane_lists', 'smarty', 'toc', 'pymdownx.extra', 'pymdownx.caret', 'pymdownx.highlight', 'pymdownx.inlinehilite', 'pymdownx.magiclink', 'pymdownx.saneheaders', 'pymdownx.tasklist', 'pymdownx.tilde']

# datetime format
datetime_format = '%Y-%m-%d %H:%M %Z'


# store config in env var
def _store():
    config = {key: val for key, val in globals().items() if not key.startswith('_')}

    _os.environ['CMS_CONFIG'] = _json.dumps(config)


# load config from env var
def _load():
    config = _json.loads(_os.environ['CMS_CONFIG'])

    globals().update(config)

    # automatically apply
    _apply()


# apply special config-specific logic after changes
def _apply():
    # setup logging
    if log:
        _logging.getLogger('cms').addHandler(_logging.FileHandler(log))
    else:
        _logging.getLogger('cms').addHandler(_logging.StreamHandler(_sys.stdout))

    _logging.getLogger('cms').setLevel(_logging.INFO)

    if http_log:
        http_log_handler = _logging.FileHandler(http_log)
        http_log_handler.setFormatter(_web.HTTPLogFormatter())

        _logging.getLogger('http').addHandler(http_log_handler)

    # automatically store if not already serialized
    if 'CMS_CONFIG' not in _os.environ:
        _store()


# load if config already serialized in env var
if 'CMS_CONFIG' in _os.environ:
    _load()
