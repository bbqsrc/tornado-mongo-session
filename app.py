import tornado.ioloop
import tornado.options
import tornado.web
import uuid
import logging

from auth import MongoAuthentication
from bson.json_util import dumps
from session import MongoSessions
from tornado.web import HTTPError, RequestHandler

class Application(tornado.web.Application):
    def __init__(self, handlers, **settings):
        tornado.web.Application.__init__(self, handlers, **settings)
        self.sessions = MongoSessions("mutiny", "sessions", timeout=1)
        self.auth = MongoAuthentication("mutiny", "authentication")
        if self.auth._coll.count() == 0:
            self.auth.register("admin", "admin", ['admin'])


class SessionMixin:
    def prepare(self):
        id = self.get_cookie('id')
        logging.debug(id)
        self.session = self.application.sessions.get_session(id)
        logging.debug(self.session)

    def begin_session(self, username, password):
        if not self.application.auth.log_in(username, password):
            return False

        data = {'username': username}
        id = self.application.sessions.new_session(data).hex
        self.session = self.application.sessions.get_session(id)
        self.set_cookie('id', id, httponly=True)
        return True

    def end_session(self):
        id = self.get_cookie('id')
        self.application.sessions.clear_session(id)
        if self.session is not None:
            username = self.session['data']['username']
            self.application.auth.log_out(username)
        self.session = None
        self.clear_cookie('id')


class UserLoginHandler(SessionMixin, RequestHandler):
    def get(self):
        page = """<!DOCTYPE html><html><head><meta charset='utf-8'><title>Log In</title></head><body>
<form method='post'>
  <fieldset>
    <legend>Log In</legend>
    <label>Username <input name='username' placeholder='Username'></label><br>
    <label>Password <input name='password' placeholder='Password' type='password'></label><br>
    <button type='submit'>Submit</button>
  </fieldset>
</form>
</body></html>"""
        self.write(page)

    def post(self):
        username = self.get_argument('username', None)
        password = self.get_argument('password', None)

        res = self.begin_session(username, password)
        if not res:
            raise HTTPError(403)
        self.redirect('/')


class UserRegisterHandler(SessionMixin, RequestHandler):
    def get(self):
        page = """<!DOCTYPE html><html><head><meta charset='utf-8'><title>Register</title></head><body>
<form method='post'>
  <fieldset>
    <legend>Register</legend>
    <label>Username <input name='username' placeholder='Username'></label><br>
    <label>Password <input name='password' placeholder='Password' type='password'></label><br>
    <button type='submit'>Submit</button>
  </fieldset>
</form>
</body></html>"""
        self.write(page)

    def post(self):
        username = self.get_argument('username', None)
        password = self.get_argument('password', None)

        res = self.application.auth.register(username, password)
        if not res:
            raise HTTPError(403)

        res = self.begin_session(username, password)
        if not res:
            raise HTTPError(403)

        self.redirect('/')


class UserLogoutHandler(SessionMixin, RequestHandler):
    def get(self):
        self.post()

    def post(self):
        self.end_session()
        self.redirect('/')


class HomeHandler(SessionMixin, RequestHandler):
    def get(self):
        if self.session is None:
            urls = '<a href="/register">Register</a> | <a href="/login">Log In</a>'
        else:
            urls = '<a href="/logout">Log Out</a>'
        page = """<!DOCTYPE html><html><head><meta charset='utf-8'><title>Mongo Session Test</title></head><body>
<div>
%s
</div>
<pre>
%s
</pre>
</body></html>""" % (urls, dumps(self.session, indent=2))
        self.write(page)

if __name__ == "__main__":
    tornado.options.parse_command_line()
    application = Application([
        (r"/", HomeHandler),
        (r"/logout", UserLogoutHandler),
        (r"/login", UserLoginHandler),
        (r"/register", UserRegisterHandler)
    ])
    application.sessions.clear_all_sessions()
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()


