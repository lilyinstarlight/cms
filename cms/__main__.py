import argparse
import logging
import signal
import sys

import fooster.web

from cms import config


def main():
    parser = argparse.ArgumentParser(description='serve up a content management system for markdown files')
    parser.add_argument('-a', '--address', dest='address', help='address to bind')
    parser.add_argument('-p', '--port', type=int, dest='port', help='port to bind')
    parser.add_argument('-t', '--template', dest='template', help='template directory to use')
    parser.add_argument('-l', '--log', dest='log', help='log directory to use')
    parser.add_argument('-b', '--blog', action='store_true', default=False, dest='blog', help='indicate whether this website is a blog')
    parser.add_argument('root', nargs='?', help='root directory to serve markdown files')

    args = parser.parse_args()

    if args.address:
        config.addr = (args.address, config.addr[1])

    if args.port:
        config.addr = (config.addr[0], args.port)

    if args.template:
        config.template = args.template

    if args.log:
        if args.log == 'none':
            config.log = None
            config.http_log = None
        else:
            config.log = args.log + '/cms.log'
            config.http_log = args.log + '/http.log'

    if args.blog:
        config.blog = args.blog

    if args.root:
        config.root = args.root


    # setup logging
    log = logging.getLogger('cms')
    log.setLevel(logging.INFO)
    if config.log:
        log.addHandler(logging.FileHandler(config.log))
    else:
        log.addHandler(logging.StreamHandler(sys.stdout))

    if config.http_log:
        http_log_handler = logging.FileHandler(config.http_log)
        http_log_handler.setFormatter(fooster.web.HTTPLogFormatter())

        logging.getLogger('http').addHandler(http_log_handler)


    from cms import name, version
    from cms import http


    log.info(name + ' ' + version + ' starting...')

    # start everything
    http.start()


    # cleanup function
    def exit(signum, frame):
        http.stop()


    # use the function for both SIGINT and SIGTERM
    for sig in signal.SIGINT, signal.SIGTERM:
        signal.signal(sig, exit)

    # join against the HTTP server
    http.join()


if __name__ == '__main__':
    main()