from google.appengine.api import users
from google.appengine.ext import db
import jinja2
import json
from lxml import etree
import os
import re
import urllib2
import webapp2


class Recipe(db.Model):
    user_id = db.StringProperty(required=True)
    url = db.StringProperty(required=True)
    title = db.StringProperty(required=True)
    ingredients = db.StringListProperty(required=True)
    steps = db.StringListProperty(required=True)
    image = db.StringProperty(required=False)


class MainHandler(webapp2.RequestHandler):
    def get(self):
        t = jinja_env.get_template('main.html')
        self.response.out.write(t.render({}))


class AddHandler(webapp2.RequestHandler):
    '''
    API handler that adds a recipe described by a JSON blob.
    '''

    def post(self):
        recipe_json = json.loads(self.request.get('recipe'))
        recipe = Recipe(
            user_id=users.get_current_user().user_id(),
            url=recipe_json['url'],
            title=recipe_json['title'],
            ingredients=recipe_json['ingredients'],
            steps=recipe_json['steps'],
            image=recipe_json['image'])
        recipe.put()


class ScrapeHandler(webapp2.RequestHandler):
    '''
    API handler that scrapes a URL and returns the found recipe as a JSON blob.
    '''

    def get(self):
        url = self.request.get('url')

        recipe = {'url': url}

        # Fetch the URL and construct an LXML tree
        result = urllib2.urlopen(url)
        parser = etree.HTMLParser()
        tree = etree.parse(result, parser)

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(
            json.dumps(self.scrape_myrecipes(recipe, tree)))

    def scrape_myrecipes(self, recipe, tree):
        title = tree.xpath('//head/title')[0].text
        title = title[:len(title) - len(' Recipe | MyRecipes.com')]
        recipe['title'] = title

        recipe['ingredients'] = []
        for e in tree.xpath('//li[@itemprop="ingredient"]'):
            ingredient = \
                e.xpath('span[@itemprop="amount"]')[0].text + ' ' + \
                e.xpath('span[@itemprop="name"]')[0].text + ' ' + \
                e.xpath('span[@itemprop="preparation"]')[0].text
            ingredient = ingredient.strip()
            ingredient = re.sub(r'\s+', ' ', ingredient)

            recipe['ingredients'] += [ingredient]

        recipe['steps'] = []
        for e in tree.xpath('//ol[@itemprop="instructions"]/li'):
            recipe['steps'] += [
                re.sub(r'^\d+\.\s+', '', e.text, flags=re.UNICODE)]

        for e in tree.xpath('//img[@alt="%s Recipe"]' % title):
            recipe['image'] = e.attrib['src']

        return recipe

app = webapp2.WSGIApplication([
        ('/', MainHandler),
        ('/api/scrape', ScrapeHandler),
        ('/api/add', AddHandler)],
    debug=True)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

# vim: ts=4 sw=4
