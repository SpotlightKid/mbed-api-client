#!/usr/bin/env python2
"""mbed compile API client.

Usage example::

    python mbed-api-client.py \
        --repo http://developer.mbed.org/users/dan/code/pubtest/ \
        --api http://developer.mbed.org \
        --user dan  \
        --target mbed-LPC1768 \
        --destdir /tmp \
        --debug 2

This will compile http://developer.mbed.org/users/dan/code/pubtest/ for the
LPC1768 target and download the result.

Examples of options::

    --extra_symbols "foo=bar,x=y"

    --replace_file "main.cpp:/tmp/replace_main.cpp"
    (can be repeated)

"""

from __future__ import print_function

import argparse
import getpass
import logging
import os
import sys
import time
from os.path import join

import requests
from distutils.util import strtobool
from six.moves import input
from six.moves.urllib.parse import urlparse

try:
    import keyring
except ImportError:
    keyring = None

log = logging.getLogger('mbedapi')


def confirm(msg):
    try:
        reply = input(msg + ' (y/N): ')
    except (EOFError, KeyboardInterrupt):
        print('')
        return False
    else:
        return(bool(strtobool))


def build_repo(args):
    payload = {
        'clean': args.clean,
        'platform': args.target,
        'repo': args.repo,
        'extra_symbols': args.extra_symbols
    }

    if args.replace_file:
        replace = []
        for pair in args.replace_file:
            dest, src = pair.split(':')
            print(dest)
            cwd = os.getcwd()

            with open(join(cwd, src), 'r') as srcfile:
                replace.append({dest: srcfile.read()})

        payload['replace'] = replace
        log.debug("Payload is: %s", payload)

    host = urlparse(args.api_url).netloc
    user = password = None

    try:
        user, host = urlparts.netloc.rsplit('@', 1)
    except:
        pass
    else:
        try:
            user, password = user.split(':', 1)
        except:
            pass

    user = args.user or user

    if not user:
        try:
            user = input('mbed username: ')
        except (EOFError, KeyboardInterrupt):
            print('')
            return 1

    if not password:
        try:
            password = keyring.get_password(host, user)
            if password is None:
                raise ValueError
        except:
            try:
                password = getpass.getpass('mbed password: ')
            except (EOFError, KeyboardInterrupt):
                print('')
                return 1

    log.debug("Auth info: host='%s' user='%s' password='%s'",
              host, user, password)

    # Send task to api
    log.debug(args.api_url + "/api/v2/tasks/compiler/start/ | data: %r",
              payload)
    r = requests.post(args.api_url + "/api/v2/tasks/compiler/start/",
                      json=payload, auth=(user, password))

    log.debug(r.content)

    if r.status_code != 200:
        raise Exception("Error while talking to the mbed API. Status: %s" %
                        r.status_code)

    if keyring and confirm("Save password for user '%s' to keyring?"):
        keyring.set_password(urlparts.netloc, args.user, password)

    uuid = r.json()['result']['data']['task_id']
    log.debug("Task accepted and given ID: %s", uuid)

    # Poll for output
    success = False
    for check in range(0, 40):
        log.debug("Checking for output: cycle %s of %s", check, 10)
        time.sleep(2)
        url = args.api_url + "/api/v2/tasks/compiler/output/%s" % uuid
        r = requests.get(url, auth=(user, password))
        log.debug(r.content)
        response = r.json()
        messages = response['result']['data']['new_messages']
        percent = 0

        for message in messages:
            if message.get('message'):
                if message.get('type') != 'debug':
                    log.info("[%s] %s", message['type'], message['message'])

            if message.get('action'):
                if message.get('percent'):
                    percent = message['percent']
                log.info("[%s%% - %s] %s", percent, message['action'],
                         message.get('file', ''))

        if response['result']['data']['task_complete']:
            log.info("Task completed.")
            success = response['result']['data']['compilation_success']
            log.info("Compile success: %s", success)
            break

    # Download binary
    if success:
        log.info("Downloading your binary")
        params = {
            'repomode': True,
            'program': response['result']['data']['program'],
            'binary': response['result']['data']['binary'],
            'task_id': uuid
        }
        r = requests.get(args.api_url + "/api/v2/tasks/compiler/bin/",
                         params=params, auth=(user, password))
        destination = join(args.destdir or os.getcwd(),
                           response['result']['data']['binary'])

        with open(destination, 'wb') as fd:
            for chunk in r.iter_content(1024):
                fd.write(chunk)

        log.info("Finished!")


def main(args=None):
    parser = argparse.ArgumentParser(description='Build an mbed repository.')
    parser.add_argument(
        '-u', '--user',
        help='Your username on mbed')
    parser.add_argument(
        '-a', '--api-url',
        type=str,
        metavar='URL',
        default='https://developer.mbed.org',
        help='URL to API server')
    parser.add_argument(
        '-t', '--target',
        required=True,
        help='Target platform name')
    parser.add_argument(
        '-d', '--destdir',
        metavar='DIR',
        help='Destination directory for firmware binary file')
    parser.add_argument(
        '-r', '--replace_file',
        action='append',
        metavar='FILEPTN',
        help=('Replace file and build. Can be repeated. '
              'Syntax: remotepath:localpath'))
    parser.add_argument(
        '-e', '--extra_symbols',
        action='append',
        metavar='SYMBOL',
        help='Provide extra symbols to build system')
    parser.add_argument(
        '-c', '--clean',
        action='store_true',
        help='Force clean build')
    parser.add_argument(
        '-D', '--debug',
        action='store_true',
        help='Show debugging info')
    parser.add_argument(
        'repo',
        metavar='REPO',
        help='URL of repository to build')

    args = parser.parse_args(sys.argv[1:] if args is None else args)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    build_repo(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
