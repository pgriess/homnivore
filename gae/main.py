from google.appengine.api import users
from google.appengine.ext import db
from homnivore.models import Recipe
from homnivore.scrape import scrape
import jinja2
import json
import os
import webapp2


class ClipHandler(webapp2.RequestHandler):
    def get(self):
        url = self.request.get('url')
        recipe = scrape(url=url, user_id=users.get_current_user().user_id())
        tmpl = jinja_env.get_template('clip.html')
        self.response.out.write(tmpl.render({'recipe': recipe}))


class AddHandler(webapp2.RequestHandler):
    '''
    API handler that adds a recipe described by a JSON blob.
    '''

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

    def get(self):
        url = self.request.get('url')

        recipe = scrape(url=url, user_id=users.get_current_user().user_id())

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(recipe.to_json())


app = webapp2.WSGIApplication([
        ('/clip', ClipHandler),
        ('/api/scrape', ScrapeHandler),
        ('/api/add', AddHandler)],
    debug=True)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

# vim: ts=4 sw=4
