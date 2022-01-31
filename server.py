import json
import os
import logging
import pycurl
from typing import Optional, Awaitable

from pip._vendor import certifi

import config as conf
import rx

# from rx import Observable
from rx import operators as ops
from rx.subject import Subject
from tornado import ioloop, curl_httpclient
from tornado.escape import json_decode
from tornado.httpclient import AsyncHTTPClient
from tornado.web import Application, RequestHandler, StaticFileHandler, url
from tornado.websocket import WebSocketHandler


AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

headers = conf.headers
GIT_ORG = conf.GITHUB_API_URL + "/orgs"


class WSHandler(WebSocketHandler):
    subject: Subject

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    orgs = conf.orgs

    def check_origin(self, origin):
        # Override to enable support for allowing alternate origins
        return True

    def get_org_repos(self, org):
        """Request the repos to the GitHub API"""
        http_client = AsyncHTTPClient()
        response = http_client.fetch(GIT_ORG + org, headers=headers, method="GET")
        return response

    def on_message(self, message):
        obj = json_decode(message)
        self.subject.on_next(obj['term'])

    def on_close(self):
        # Unsubscribe from observable
        # will stop the work of all observable
        self.combine_latest_sbs.dispose()
        print("WebSocket closed")

    def open(self):
        print("WebSocket opened")
        self.write_message("Connection Opened")

        def send_response(x):
            self.write_message(json.dumps(x))

        def on_error(ex):
            print(ex)

        self.subject = Subject()

        user_input = self.subject.pipe(
            ops.take_last_with_time(1000),  # Given the last value in a given time interval
            ops.start_with(''),  # Immediately after the subscription sends the default value
            ops.filter(lambda text: not text or len(text) > 2)
        )
        # .take_last_with_time(
        #     1000  # Given the last value in a given time interval
        # ).start_with(
        #     ''  # Immediately after the subscription sends the default value
        # ).filter(
        #     lambda text: not text or len(text) > 2
        # )

        interval_obs = rx.interval(60.0).pipe(
            ops.start_with(0)
        )
        #     Observable.pipe(
        #     ops.interval(60.0),  # refresh the value every 60 seconds for periodic updates
        #     ops.start_with(0)
        # )
        # interval(
        #     60000  # refresh the value every 60 seconds for periodic updates
        # ).start_width(0)

        self.combine_latest_sbs = user_input.pipe(
            ops.combine_latest(interval_obs),
            # ops.combine_latest(interval_obs, lambda input_val, i: input_val),
            ops.do_action(lambda x: send_response("clear")),
            ops.flat_map(self.get_data)
        ).subscribe(send_response, on_error)

    def get_info(self, req):
        """Managing error codes and returning a list of json with content"""

        if req.code == 200:
            jsresponse = json.loads(req.body)
            return jsresponse
        elif req.code == 403:
            print("403 error")
            jsresponse = json.loads(req.body)
            return json.dumps("clear")
        else:
            return json.dumps("failed")

    def get_data(self, query):
        """Query the data to the API and return the content filtered"""

        return rx.from_list(self.orgs).pipe(
            ops.flat_map(lambda name: rx.from_future(self.get_org_repos(name))),
            ops.flat_map(
                lambda x: rx.from_list(self.get_info(x)).pipe(
                    ops.filter(
                        lambda val: (val.get("description") is not None and (val.get("description").lower()).find(
                            query.lower()) != -1) or
                                    (val.get("language") is not None and (val.get("language").lower()).find(
                                        query.lower()) != -1)
                    ),
                    ops.take(10)
                )
            ),
            ops.map(lambda x: {'name': x.get("name"),
                               'stars': str(x.get("stargazers_count")),
                               'link': x.get("svn_url"),
                               'description': x.get("description"),
                               'language': x.get("language")})
        )
        #     .flat_map(
        #     lambda name: rx.from_future(self.get_org_repos(name))
        # ).flat_map(
        #     lambda x: rx.from_list(
        #         self.get_info(x)
        #     ).filter(
        #         lambda val: (val.get("description") is not None and (val.get("description").lower()).find(query.lower()) != -1) or
        #                     (val.get("language") is not None and (val.get("language").lower()).find(query.lower()) != -1)
        #     ).take(10)
        # ).map(lambda x: {'name': x.get("name"),
        #                  'stars': str(x.get("stargazers_count")),
        #                  'link': x.get("svn_url"),
        #                  'description': x.get("description"),
        #                  'language': x.get("language")})


class MainHandler(RequestHandler):
    def get(self):
        self.render("index.html")


def main():
    port = os.environ.get("PORT", 8080)
    app = Application([
        url(r"/", MainHandler),
        (r'/ws', WSHandler),
        (r'/static/(.*)', StaticFileHandler, {'path': "."})
    ])

    print("Starting server at port: %s" % port)
    app.listen(port)
    ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
