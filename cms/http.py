import collections
import datetime
import json
import os
import os.path

import markdown

import fooster.web
import fooster.web.file
import fooster.web.page

from cms import config


if config.blog:
    import feedgen.feed


resource = r'(?P<path>/[/a-zA-Z0-9._-]*)'
page = r'(?P<page>/[/a-zA-Z0-9._-]*(?:\.md)?)'
atom = r'(?P<page>/[/a-zA-Z0-9._-]*)atom\.xml'
rss = r'(?P<page>/[/a-zA-Z0-9._-]*)rss\.xml'

http = None

routes = collections.OrderedDict()
error_routes = {}


def extract_title(file):
    title = file.readline()

    title = title.strip()

    if title[0] == '#':
        title = title[1:]
    else:
        file.readline()

    title = title.strip()

    return title


def extract_content(file):
    return markdown.markdown(file.read(), extensions=['markdown.extensions.' + extension for extension in config.extensions], output_format='xhtml5')


class Resource(fooster.web.file.PathHandler):
    local = config.template + '/res'
    remote = '/res'


class PageResource(Resource):
    local = config.root
    remote = '/'

    def respond(self):
        self.pathstr = self.groups['page'] + '.res' + self.groups['path']

        return super().respond()


class Page(fooster.web.page.PageHandler):
    directory = config.template
    page = 'post.html' if config.blog else 'page.html'

    def respond(self):
        norm_request = fooster.web.file.normpath(self.groups['page'])
        if not self.groups['page'] or self.groups['page'] != norm_request:
            if not norm_request:
                norm_request = '/'

            self.response.headers.set('Location', norm_request)

            return 307, ''

        if config.blog and self.groups['page'].endswith('/'):
            self.page = 'index.html'

        return super().respond()

    def format(self, output):
        page = self.groups['page']

        if page.endswith('.md'):
            try:
                self.response.headers.set('Content-Type', 'text/markdown')
                return open(config.root + page, 'rb')
            except FileNotFoundError:
                raise fooster.web.HTTPError(404)
        elif page.endswith('/'):
            if config.blog:
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
                    raise fooster.web.HTTPError(404)

                index += '\n</ul>'

                return output.format(index=index)
            else:
                page += 'index'

        try:
            path = config.root + page + '.md'

            with open(path, 'r') as file:
                title = extract_title(file)
                content = extract_content(file)

            time = datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        except FileNotFoundError:
            raise fooster.web.HTTPError(404)

        return output.format(title=title, time=time, content=content)


class Feed(fooster.web.HTTPHandler):
    format = 'Atom'

    def do_get(self):
        if not config.blog:
            raise fooster.web.HTTPError(404)

        norm_request = fooster.web.file.normpath(self.groups['page'])
        if not self.groups['page'] or self.groups['page'] != norm_request:
            if not norm_request:
                norm_request = '/'

            self.response.headers.set('Location', norm_request)

            return 307, ''

        directory = self.groups['page']

        try:
            with open(config.root + directory + '/feed.json', 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            raise fooster.web.HTTPError(404)

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

        updated = None

        for filename in files:
            if filename.endswith('.md'):
                fe = fg.add_entry()

                href = directory + filename
                path = config.root + href

                with open(path, 'r') as file:
                    fe.title(extract_title(file))
                    fe.content(extract_content(file), src=href)

                fe.id(href)

                date = datetime.datetime.fromtimestamp(os.path.getmtime(path), datetime.timezone.utc)
                fe.published(date)
                fe.updated(date)

                if not updated or date > updated:
                    updated = date

        fg.updated(updated)

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


class ErrorPage(fooster.web.page.PageErrorHandler):
    directory = config.template
    page = 'error.html'


routes = collections.OrderedDict([('/res' + resource, Resource), (page + '/res' + resource, PageResource), (atom, Atom), (rss, RSS), (page, Page)])
error_routes.update(fooster.web.page.new_error(handler=ErrorPage))


def start():
    global http

    http = fooster.web.HTTPServer(config.addr, routes, error_routes)
    http.start()


def stop():
    global http

    http.stop()
    http = None


def join():
    global http

    http.join()
