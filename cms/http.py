import mimetypes
import os
import time
import urllib.parse

import markdown

import web, web.file, web.page

from cms import config, log


resource = '([/a-zA-Z0-9._-]+)'
page = '([/a-zA-Z0-9_-]+(?:\.md)?)'

http = None

routes = {}
error_routes = {}


class Resource(web.file.FileHandler):
    local = os.path.dirname(__file__) + '/res'
    remote = '/res'
    fileidx = 0

    def respond(self):
        norm_request = web.file.normpath(self.groups[self.fileidx])
        if self.groups[self.fileidx] != norm_request:
            self.response.headers.set('Location', self.remote + norm_request)

            return 307, ''

        self.filename = self.local + urllib.parse.unquote(self.groups[self.fileidx])

        return super().respond()


class PageResource(Resource):
    fileidx = 1

    def respond(self):
        page = self.groups[0]

        self.local = config.root + page + '.res'
        self.remote = page + '/res'

        return super().respond()


class Page(web.page.PageHandler):
    directory = os.path.dirname(__file__) + '/html'
    page = 'page.html'

    def format(self, output):
        page = self.groups[0]

        if page.endswith('.md'):
            try:
                self.response.headers.set('Content-Type', 'text/markdown')
                return open(config.root + page, 'rb')
            except FileNotFoundError:
                raise web.HTTPError(404)
        elif page.endswith('/'):
            page += 'index'

        try:
            with open(config.root + page + '.md', 'r') as file:
                title = file.readline()

                title.strip()

                if title[0] == '#':
                    title = title[1:]
                else:
                    file.readline()

                title.strip()

                mdcontent = file.read()
        except FileNotFoundError:
            raise web.HTTPError(404)

        content = markdown.markdown(mdcontent, extensions=['markdown.extensions.' + extension for extension in config.extensions], output_format='xhtml5')

        return output.format(title=title, content=content)


class ErrorPage(web.page.PageErrorHandler):
    directory = os.path.dirname(__file__) + '/html'
    page = 'error.html'


routes.update({'/res' + resource: Resource, page + '/res' + resource: PageResource, page: Page})
error_routes.update(web.page.new_error(handler=ErrorPage))


def start():
    global http

    http = web.HTTPServer(config.addr, routes, error_routes, log=log.httplog)
    http.start()


def stop():
    global http

    http.stop()
    http = None
