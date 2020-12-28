import collections
import datetime
import html
import html.parser
import json
import os

import dateutil.parser
import dateutil.tz

import pygments.formatters

import markdown

import fooster.web
import fooster.web.file
import fooster.web.page

from cms import config


if config.blog:
    import feedgen.feed


resource = r'(?P<path>/[/a-zA-Z0-9._-]*)'
page = r'(?P<page>/[/a-zA-Z0-9._-]*(?:\.md)?)'
atom = r'(?P<page>/(?:[/a-zA-Z0-9._-]*/|))feed\.atom'
rss = r'(?P<page>/(?:[/a-zA-Z0-9._-]*/|))feed\.rss'

http = None

routes = collections.OrderedDict()
error_routes = {}


class HTMLTextExtractor(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)

        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def handle_entityref(self, name):
        self.text.append('&{};'.format(name))

    def handle_charref(self, num):
        self.text.append('&#{};'.format(num))

    def get_text(self):
        return ''.join(self.text)


def clean(markup):
    extractor = HTMLTextExtractor()
    extractor.feed(markup)
    extractor.close()

    return extractor.get_text()


def render(content):
    return markdown.markdown(content, extensions=config.extensions, output_format='xhtml')


def extract_title(file):
    title = file.readline()
    while title and not title.strip():
        title = file.readline()

    title = title.strip()

    if title[0] == '#':
        title = title[1:]
    else:
        file.readline()

    title = title.strip()

    rendered = render(title)
    if rendered.startswith('<p>') and rendered.endswith('</p>'):
        rendered = rendered[3:-4]

    return rendered


def extract_datetime(file):
    pos = file.tell()

    date = file.readline()
    while date and not date.strip():
        date = file.readline()

    time = None

    if not time and date.startswith('Date:'):
        try:
            time = dateutil.parser.isoparse(date[5:].strip()).astimezone(dateutil.tz.gettz(config.timezone))
        except ValueError:
            pass

    if not time:
        time = datetime.datetime.fromtimestamp(os.fstat(file.fileno()).st_mtime, datetime.timezone.utc).astimezone(dateutil.tz.gettz(config.timezone))

        file.seek(pos)

    return time


def extract_content(file):
    return render(file.read())


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

        if self.groups['page'].endswith('/'):
            if config.blog:
                self.page = 'posts.html'
            else:
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
                try:
                    with open(config.root + page + 'meta.json', 'r') as file:
                        meta = json.load(file)
                except FileNotFoundError:
                    meta = {'title': '', 'subtitle': '', 'author': {'name': '', 'email': ''}}

                index = '<ul>'

                try:
                    files = [filename for filename in os.listdir(config.root + page)]
                    posts = []

                    for filename in files:
                        if filename.endswith('.md'):
                            href = page + filename[:-3]
                            path = config.root + page + filename

                            with open(path, 'r') as file:
                                title = extract_title(file)
                                time = extract_datetime(file)

                            posts.append({'href': href, 'title': title, 'datetime': time})
                except FileNotFoundError:
                    raise fooster.web.HTTPError(404)

                if len(posts) == 0:
                    raise fooster.web.HTTPError(404)

                posts.sort(key=lambda post: post['datetime'], reverse=True)

                for post in posts:
                    index += '\n<li><h3><a href="{href}">{title}</a></h3><time datetime="{datetime}">{time}</time></li>'.format(href=post['href'], title=post['title'], datetime=post['datetime'].isoformat(timespec='milliseconds'), time=html.escape(post['datetime'].strftime(config.datetime_format)))

                index += '\n</ul>'

                return output.format(title_clean=clean(meta['title']), title=html.escape(meta['title']), subtitle=html.escape(meta['subtitle']), author_name=html.escape(meta['author']['name']), author_email=html.escape(meta['author']['email']), posts=index)
            else:
                page += 'index'
        try:
            path = config.root + page + '.md'

            with open(path, 'r') as file:
                title = extract_title(file)
                time = extract_datetime(file)
                content = extract_content(file)
        except FileNotFoundError:
            raise fooster.web.HTTPError(404)

        return output.format(title_clean=clean(title), title=title, style=pygments.formatters.HtmlFormatter().get_style_defs('.highlight'), datetime=time.isoformat(timespec='milliseconds'), time=html.escape(time.strftime(config.datetime_format)), content=content)


class Feed(fooster.web.HTTPHandler):
    format = 'Atom'

    def respond(self):
        if not config.blog:
            raise fooster.web.HTTPError(404)

        norm_request = fooster.web.file.normpath(self.groups['page'])
        if not self.groups['page'] or self.groups['page'] != norm_request:
            if not norm_request:
                norm_request = '/'

            self.response.headers.set('Location', norm_request)

            return 307, ''

        return super().respond()

    def do_get(self):
        directory = self.groups['page']

        try:
            with open(config.root + directory + 'meta.json', 'r') as file:
                meta = json.load(file)
        except FileNotFoundError:
            raise fooster.web.HTTPError(404)

        fg = feedgen.feed.FeedGenerator()

        fg.id(directory)
        fg.title(meta['title'])
        fg.subtitle(meta['subtitle'])
        fg.author(meta['author'])
        fg.link(href=directory)

        if 'link' in meta:
            fg.link(meta['link'])

        if 'logo' in meta:
            fg.logo(meta['logo'])

        if 'language' in meta:
            fg.language(meta['language'])

        if 'rights' in meta:
            fg.rights(meta['rights'])

        files = [filename for filename in os.listdir(config.root + directory)]
        posts = []

        for filename in files:
            if filename.endswith('.md'):
                href = directory + filename[:-3]
                path = config.root + directory + filename

                with open(path, 'r') as file:
                    title = extract_title(file)
                    time = extract_datetime(file)
                    content = extract_content(file)

                posts.append({'href': href, 'title': title, 'datetime': time, 'content': content})

        posts.sort(key=lambda post: post['datetime'])

        updated = None

        for post in posts:
            fe = fg.add_entry()

            fe.title(post['title'])
            fe.published(post['datetime'])
            fe.updated(post['datetime'])
            fe.content(post['content'], type='html')
            fe.link(href=post['href'])

            fe.id(post['href'])

            if not updated or post['datetime'] > updated:
                updated = post['datetime']

        fg.updated(updated)

        if self.format == 'Atom':
            return 200, fg.atom_str(pretty=True)
        elif self.format == 'RSS':
            return 200, fg.rss_str(pretty=True)
        else:
            raise NotImplementedError()


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
