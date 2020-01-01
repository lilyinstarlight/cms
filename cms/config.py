# address to listen on
addr = ('', 8000)

# log locations
log = '/var/log/cms/cms.log'
http_log = '/var/log/cms/http.log'

# template directory to use
import os.path
template = os.path.dirname(__file__) + '/html'

# root directory of markdown files
root = '/var/www/cms'

# whether this website is a blog
blog = False

# markdown extensions
extensions = ['extra', 'codehilite', 'smarty', 'toc']

# datetime format
datetime_format = '%Y-%m-%d %H:%M %Z'

# datetime timezone
datetime_tz = 'UTC'
