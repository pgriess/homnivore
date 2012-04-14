from google.appengine.api import users
from google.appengine.ext import db
from homnivore.models import Recipe
from homnivore.scrape import scrape
import jinja2
import json
import logging
import os
from urlparse import urlparse
import webapp2

def login_required(f):
    '''
    Decorator to indicate that the given function requires a logged-in user.
    This should be applied to get()/post()/etc methods in RequestHandler
    objects.
    '''

    def wrapper_f(self, *args, **kwargs):
        if not users.get_current_user():
            self.redirect(users.create_login_url(self.request.url))
            return

        f(self, *args, **kwargs)

    return wrapper_f


def render_template(path, **kwargs):
    '''
    Render a temlate at the given path, creating a dictionary out of
    the specified keyword arguemnts.
    '''

    ctx = {}
    if users.get_current_user():
        ctx['logout_url'] = users.create_logout_url('/')
    else:
        ctx['login_url'] = users.create_login_url('/')

    ctx.update(kwargs)

    return jinja_env.get_template(path).render(ctx)


class MainHandler(webapp2.RequestHandler):
    def get(self):
        if users.get_current_user():
            self.redirect('/list')
            return

        self.response.out.write(render_template('main.html'))


class ListHandler(webapp2.RequestHandler):
    def get(self):
        recipes = Recipe.all()
        recipes.filter('user_id = ', users.get_current_user().user_id())
        tmpl = jinja_env.get_template('list.html')
        self.response.out.write(
            render_template('list.html',
                recipes=recipes,
                base_url=self.request.host_url))


class ClipHandler(webapp2.RequestHandler):
    @login_required
    def get(self):
        url = self.request.get('url')
        recipe = scrape(url=url, user_id=users.get_current_user().user_id())
        if not recipe:
            logging.info('Failed to scrape ' + url)
        self.response.out.write(
            render_template('clip.html',
                recipe=recipe,
                url=urlparse(url)))


class ViewHandler(webapp2.RequestHandler):
    @login_required
    def get(self):
        key = db.Key(self.request.get('id'))
        recipe = Recipe.get(key)
        self.response.out.write(
            render_template('view.html',
                recipe=recipe))


class AddHandler(webapp2.RequestHandler):
    '''
    API handler that adds a recipe described by a JSON blob.
    '''

    @login_required
    def post(self):
        recipe = Recipe.from_json(self.request.get('recipe'))
       
        # Make sure nobody tries to write to someone else's stream
        if recipe.user_id != users.get_current_user().user_id():
            self.error(400)
            return

        recipe.put()


class ScrapeHandler(webapp2.RequestHandler):
    '''
    API handler that scrapes a URL and returns the found recipe as a JSON blob.
    '''

    @login_required
    def get(self):
        url = self.request.get('url')

        recipe = scrape(url=url, user_id=users.get_current_user().user_id())
        if not recipe:
            logging.info('Failed to scrape ' + url)
            self.error(400)
            return

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(recipe.to_json())


app = webapp2.WSGIApplication([
        ('/', MainHandler),
        ('/list', ListHandler),
        ('/clip', ClipHandler),
        ('/view', ViewHandler),
        ('/api/scrape', ScrapeHandler),
        ('/api/add', AddHandler)],
    debug=True)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

# vim: ts=4 sw=4
