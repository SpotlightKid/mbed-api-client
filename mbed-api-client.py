#!/usr/bin/env python2
"""mbed compile API client.

Usage example::

    python mbed-api-client.py \
        --repo http://developer.mbed.org/users/dan/code/pubtest/ \
        --api http://developer.mbed.org \
        --user dan  \
        --platform mbed-LPC1768 \
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
import json
import logging
import os
import sys
import time
from os.path import join

import requests

log = logging.getLogger('mbedapi')


def build_repo(args):
    payload = {
        'clean': args.clean,
        'platform': args.platform,
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

        payload['replace'] = json.dumps(replace)
        log.debug("Payload is: %s", payload)

    auth = (args.user, getpass.getpass('mbed password: '),)

    # Send task to api
    log.debug("%s/api/v2/tasks/compiler/start/ | data: %r", args.api, payload)
    r = requests.post(args.api + "/api/v2/tasks/compiler/start/",
                      data=payload, auth=auth)

    log.debug(r.content)

    if r.status_code != 200:
        raise Exception("Error while talking to the mbed API. Status: %s" %
                        r.status_code)

    uuid = r.json()['result']['data']['task_id']
    log.debug("Task accepted and given ID: %s", uuid)

    # Poll for output
    success = False
    for check in range(0, 40):
        log.debug("Checking for output: cycle %s of %s", check, 10)
        time.sleep(2)
        r = requests.get(args.api + "/api/v2/tasks/compiler/output/%s" % uuid,
                         auth=auth)
        log.debug(r.content)
        response = json.loads(r.content)
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
        r = requests.get(args.api + "/api/v2/tasks/compiler/bin/",
                         params=params, auth=auth)
        destination = join(args.destdir, response['result']['data']['binary'])

        with open(destination, 'wb') as fd:
            for chunk in r.iter_content(1024):
                fd.write(chunk)

        log.info("Finished!")


def main(args=None):
    parser = argparse.ArgumentParser(description='Build an mbed repository.')
    parser.add_argument(
        '--user',
        required=True,
        type=str,
        help='Your username on mbed')
    parser.add_argument(
        '--api',
        type=str,
        default='https://developer.mbed.org',
        help='URL to API server')
    parser.add_argument(
        '--repo',
        required=True,
        type=str,
        help='URL of repository to build')
    parser.add_argument(
        '--platform',
        required=True,
        type=str,
        help='Platform name')
    parser.add_argument(
        '--destdir',
        required=True,
        type=str,
        help='Binary destination directory')
    parser.add_argument(
        '--replace_file',
        type=str,
        action='append',
        help=('Replace file and build. Can be repeated.'
              'Syntax: remotepath:localpath'))
    parser.add_argument(
        '--extra_symbols',
        type=str,
        action='append',
        help='Provide extra symbols to build system')
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Force clean build')
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Show debugging info')

    args = parser.parse_args(sys.argv[1:] if args is None else args)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    build_repo(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
