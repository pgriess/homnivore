import jinja2
import json
from lxml import etree
import os
import re
import urllib2
import webapp2

class MainHandler(webapp2.RequestHandler):
    def get(self):
        t = jinja_env.get_template('main.html')
        self.response.out.write(t.render({}))

class ScrapeHandler(webapp2.RequestHandler):
    '''
    API that fetches a URL to be scraped and returns its HTML, munged such that
    original JavaScript is expunged and our own JavaScript inserted to do the
    actual scraping.

    The result of the scrape is poked into the parent window's 'result' object.
    I am a terrible human being.
    '''

    def get(self):
        url = self.request.get('url')

        # Fetch the URL and construct an LXML tree
        result = urllib2.urlopen(url)
        parser = etree.HTMLParser()
        tree = etree.parse(result, parser)

        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(
            json.dumps(self.scrape_myrecipes(tree)))

    def scrape_myrecipes(self, tree):
        recipe = {}

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

        return recipe

app = webapp2.WSGIApplication([
        ('/', MainHandler),
        ('/api/scrape', ScrapeHandler)],
    debug=True)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

# vim: ts=4 sw=4
