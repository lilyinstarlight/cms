import datetime
import json
import mimetypes
import os
import os.path
import time
import urllib.parse

import markdown

import web, web.file, web.page

from cms import config, log


if config.blog:
    import feedgen.feed


resource = '([/a-zA-Z0-9._-]+)'
page = '(?!/res)([/a-zA-Z0-9._-]+(?:\.md)?(?!\.xml))'
atom = '(?!/res)([/a-zA-Z0-9._-]+)atom\.xml'
rss = '(?!/res)([/a-zA-Z0-9._-]+)rss\.xml'

http = None

routes = {}
error_routes = {}


def extract_title(file):
    title = file.readline()

    title.strip()

    if title[0] == '#':
        title = title[1:]
    else:
        file.readline()

    title.strip()

    return title


def extract_content(file):
    return markdown.markdown(file.read(), extensions=['markdown.extensions.' + extension for extension in config.extensions], output_format='xhtml5')


class Resource(web.file.FileHandler):
    local = config.template + '/res'
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
    directory = config.template
    page = 'page.html'

    def respond(self):
        if config.blog and self.groups[0].endswith('/'):
            self.page = 'index.html'

        return super().respond()

    def format(self, output):
        page = self.groups[0]

        if page.endswith('.md'):
            try:
                self.response.headers.set('Content-Type', 'text/markdown')
                return open(config.root + page, 'rb')
            except FileNotFoundError:
                raise web.HTTPError(404)
        elif page.endswith('/'):
            if not config.blog:
                page += 'index'
            else:
                index = '<ul>'

                try:
                    files = [filename for filename in os.listdir(config.root + page)]
                    files.sort(key=lambda filename: os.path.getmtime(config.root + page + filename), reverse=True)

                    for filename in files:
                        if filename.endswith('.md'):
                            href = page + filename[:-3]
                            path = config.root + page + filename

                            with open(path, 'r') as file:
                                title = extract_title(file)

                            time = datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

                            index += '\n<li><h3><a href="{href}">{title}</a></h3><time>{time}</time></li>'.format(href=href, title=title, time=time)
                except FileNotFoundError:
                    raise web.HTTPError(404)

                index += '\n</ul>'

                return output.format(index=index)

        try:
            path = config.root + page + '.md'

            with open(path, 'r') as file:
                title = extract_title(file)
                content = extract_content(file)

            time = datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        except FileNotFoundError:
            raise web.HTTPError(404)

        return output.format(title=title, time=time, content=content)


class Feed(web.HTTPHandler):
    format = 'Atom'

    def do_get(self):
        if not config.blog:
            raise web.HTTPError(404)

        directory = self.groups[0]

        try:
            with open(config.root + directory + '/feed.json', 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            raise web.HTTPError(404)

        fg = feedgen.feed.FeedGenerator()

        fg.id(directory)
        fg.title(data['title'])
        fg.subtitle(data['subtitle'])
        fg.author(data['author'])
        fg.link(href=directory)

        if 'link' in data:
            fg.link(data['link'])

        if 'logo' in data:
            fg.logo(data['logo'])

        if 'language' in data:
            fg.language(data['language'])

        if 'rights' in data:
            fg.rights(data['rights'])

        files = [filename for filename in os.listdir(config.root + directory)]
        files.sort(key=lambda filename: os.path.getmtime(config.root + directory + filename), reverse=True)

        for filename in files:
            if filename.endswith('.md'):
                fe = fg.add_entry()

                href = directory + filename
                path = config.root + href

                with open(path, 'r') as file:
                    fe.title(extract_title(file))
                    fe.content(extract_content(file), src=href)

                fe.id(href)

                fe.published(datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc))

        if self.format == 'Atom':
            return 200, fg.atom_str(pretty=True)
        elif self.format == 'RSS':
            return 200, fg.rss_str(pretty=True)
        else:
            raise NotImplementedError


class Atom(Feed):
    format = 'Atom'


class RSS(Feed):
    format = 'RSS'


class ErrorPage(web.page.PageErrorHandler):
    directory = config.template
    page = 'error.html'


routes.update({'/res' + resource: Resource, page + '/res' + resource: PageResource, page: Page, atom: Atom, rss: RSS})
error_routes.update(web.page.new_error(handler=ErrorPage))


def start():
    global http

    http = web.HTTPServer(config.addr, routes, error_routes, log=log.httplog)
    http.start()


def stop():
    global http

    http.stop()
    http = None
