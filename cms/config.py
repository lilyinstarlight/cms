# address to listen on
addr = ('', 8080)

# log locations
log = '/var/log/cms/cms.log'
httplog = '/var/log/cms/http.log'

# root directory of markdown files
root = '/var/www/cms'

# template directory to use
import os.path
template = os.path.dirname(__file__) + '/html'

# markdown extensions
extensions = ['extra', 'codehilite', 'smarty', 'toc']
