"""

Usage example:

python mbedapi.py  --repo http://developer.mbed.org/users/dan/code/pubtest/ --user dan --api http://developer.mbed.org --platform mbed-LPC1768 --destdir /tmp/ --debug 2

#This will compile http://developer.mbed.org/users/dan/code/pubtest/ for the 1768 and download the result.

Examples of options:
--extra_symbols "foo=bar,x=y" 

--replace_file "main.cpp:/tmp/replace_main.cpp"  
(can be repeated)

"""
import os, getpass, sys, json, time, requests, logging


def build_repo(args):

    payload = {'clean':args.clean, 'platform':args.platform, 'repo':args.repo, 'extra_symbols': args.extra_symbols}

    if args.replace_file:
        replace = []
        for pair in args.replace_file:
            dest = pair.split(':')[0]
            src = pair.split(':')[1]
            print dest
            cwd = os.getcwd()
            srcfile = open(os.path.join(cwd, src), 'r')
            replace.append({dest:srcfile.read()})

        payload['replace'] = json.dumps(replace)
        logging.debug("Payload is: %s"%payload)

    auth = (args.user, getpass.getpass('mbed password: '),)

    #send task to api
    logging.debug(args.api + "/api/v2/tasks/compiler/start/" + "| data: " + str(payload))
    r = requests.post(args.api + "/api/v2/tasks/compiler/start/", data=payload, auth=auth)

    logging.debug(r.content)

    if r.status_code != 200:
        raise Exception("Error while talking to the mbed API")

    uuid = json.loads(r.content)['result']['data']['task_id']
    logging.debug("Task accepted and given ID: %s"%uuid)
    success = False


    #poll for output
    for check in range(0,40):
        logging.debug("Checking for output: cycle %s of %s"%(check, 10))
        time.sleep(2)
        r = requests.get(args.api + "/api/v2/tasks/compiler/output/%s"%uuid, auth=auth)
        logging.debug(r.content)
        response = json.loads(r.content)
        messages = response['result']['data']['new_messages']
        percent = 0
        for message in messages:
            if message.get('message'):
                if message.get('type') != 'debug':
                    logging.info("[%s] %s"%(message['type'], message['message']))
            if message.get('action'):
                if message.get('percent'):
                    percent = message['percent']
                logging.info("[%s%% - %s] %s "%(percent, message['action'], message.get('file', '')))

        if response['result']['data']['task_complete']:
            logging.info("Task completed.")
            success = response['result']['data']['compilation_success']
            logging.info("Compile success: %s"%(success))
            break

    #now download
    if success:
        logging.info("Downloading your binary")
        params = {
                'repomode': True,
                'program': response['result']['data']['program'],
                'binary': response['result']['data']['binary'],
                'task_id': uuid }
        r = requests.get(args.api + "/api/v2/tasks/compiler/bin/", params=params, auth=auth)
        destination = os.path.join(args.destdir, response['result']['data']['binary'])

        with open(destination, 'wb') as fd:
            for chunk in r.iter_content(1024):
                fd.write(chunk)

        logging.info("Finished!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Build an mbed repository.')
    parser.add_argument('--user', type=str, help='Your username on mbed.', required=True)
    parser.add_argument('--api', type=str, help='URL to API server', required=True, default='https://developer.mbed.org')
    parser.add_argument('--repo', type=str, help='URL of repository to build.', required=True)
    parser.add_argument('--platform', type=str, help='Platform name', required=True)
    parser.add_argument('--destdir', type=str, help='Binary destination directory', required=True)
    parser.add_argument('--replace_file', type=str, help='Replace file and build. Can be repeated. Syntax: remotepath:localpath', required=False, action='append')
    parser.add_argument('--extra_symbols', type=str, help='Provide extra symbols to build system', required=False, action='append')
    parser.add_argument('--clean', action='store_true', help='Force clean build')
    parser.add_argument('--debug', help='Show debugging info', required=False)

    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    build_repo(args)


