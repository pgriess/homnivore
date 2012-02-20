'''
Wrapper around the FatSecret REST API

http://platform.fatsecret.com/api/
'''

import json
import oauth2
import urllib

class FatSecret(object):

    _REST_ENDPOINT = 'http://platform.fatsecret.com/rest/server.api'
    
    def __init__(self, consumerKey, secretKey):
        self.oaClient = oauth2.Client(oauth2.Consumer(consumerKey, secretKey))

    def __getattr__(self, name):
        def wrapper_f(**kwargs):
            kwargs.update({
                'method': name.replace('_', '.'),
                'format': 'json'})

            head, body = self.oaClient.request(
                uri=self._REST_ENDPOINT,
                method='POST',
                body=urllib.urlencode(kwargs))
            
            body = json.loads(body)

            if 'error' in body:
                raise FatSecretError(
                    code=body['error']['code'],
                    message=body['error']['message'])

            return body

        return wrapper_f


class FatSecretError(Exception):
    
    def __init__(self, code, message):
        self.code = code
        self.message = message


if __name__ == '__main__':
    from optparse import OptionParser
    import sys

    op = OptionParser(
        usage='%prog [options] <consumer-key> <secret-key> <method>',
        description='''Commandline wrapper around FatSecret API.
        
Consumes a JSON object on stdin and writes a JSON object to stdout. Headers are
written to stderr as a JSON object.''')
    
    opts, args = op.parse_args()
    
    if len(args) < 1:
        op.error('no consumer key specified')
    consumerKey = args[0]

    if len(args) < 2:
        op.error('no secret key specified')
    secretKey = args[1]

    if len(args) < 3:
        op.error('no method specified')
    method = args[2]

    data = json.loads(''.join(sys.stdin.readlines()))

    fs = FatSecret(consumerKey, secretKey)
    body = getattr(fs, method)(**data)

    print json.dumps(body)
