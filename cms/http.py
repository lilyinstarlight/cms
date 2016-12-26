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
page = '([/a-zA-Z0-9_-]+(?:\.md)?)'
atom = '([/a-zA-Z0-9_-]+(?:atom\.xml)?)'
rss = '([/a-zA-Z0-9_-]+(?:rss\.xml)?)'

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
                content = '<ul>'

                for filename in os.listdir(config.root + page):
                    if filename.endswith('.md'):
                        href = page + filename[:-3]
                        path = config.root + page + filename

                        with open(path, 'r') as file:
                            title = extract_title(file)

                        date = datetime.datetime.fromtimestamp(os.path.ctime(path)).strftime('%Y-%m-%d %H:%M UTC')

                        content += '\n<li><a href="{href}">{title} - {date}</a></li>'.format(href=href, title=title, date=date)

                content += '\n</ul>'

                return output.format(title='Index', content=content)

        try:
            with open(config.root + page + '.md', 'r') as file:
                title = extract_title(file)
                content = extract_content(file)
        except FileNotFoundError:
            raise web.HTTPError(404)

        return output.format(title=title, content=content)


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
        fg.author(data['author'])

        if 'link' in data:
            fg.link(data['link'])

        if 'logo' in data:
            fg.logo(data['logo'])

        if 'subtitle' in data:
            fg.subtitle(data['subtitle'])

        if 'language' in data:
            fg.language(data['language'])

        if 'rights' in data:
            fg.rights(data['rights'])

        for filename in os.listdir(config.root + directory):
            if filename.endswith('.md'):
                fe = fg.add_entry()

                href = directory + '/' + filename
                path = config.root + href

                with open(path, 'r') as file:
                    fe.title(extract_title(file))
                    fe.content(extract_content(file), src=href)

                fe.id(href)

                fe.published(datetime.datetime.fromtimestamp(os.path.ctime(path)))

        if self.format == 'Atom':
            return fg.atom_str(pretty=True)
        elif self.format == 'RSS':
            return fg.rss_str(pretty=True)
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
