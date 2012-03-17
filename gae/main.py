import jinja2
from lxml import etree
import os
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

        # Remove all JavaScript
        #
        # XXX: What about onload and the like?
        for e in tree.xpath('//script'):
            e.clear()

        # Insert our own JavaScript
        #
        # XXX: Be way less clowny. This only works on myrecipes.com, and even
        #      then it probably doesn't work for all the recipes.
        h = tree.xpath('//head')[0]
        etree.SubElement(h, 'script',
            src='https://ajax.googleapis.com/ajax/libs/jquery/1.7.1/jquery.min.js')
        s = etree.SubElement(h, 'script')
        s.text = '''
    $(document).ready(function() {
        var result = {}

        var title = $("title").text();
        title = title.substring(0, title.length - " | MyRecipes.com".length);
        result.title = title;

        result.ingredients = Array();
        $("li[itemprop=\\"ingredient\\"]").each(function(idx, elt) {
            var ingredient = 
                $("span[itemprop=\\"amount\\"]", elt).text() + " " +
                $("span[itemprop=\\"name\\"]", elt).text() + " " +
                $("span[itemprop=\\"preparation\\"]", elt).text();
            ingredient = ingredient.trim();
            ingredient = ingredient.replace(/\s+/g, " ");

            result.ingredients.push(ingredient);
        });

        result.steps = Array();
        $("ol[itemprop=\\"instructions\\"] li").each(function(idx, elt) {
            var step = $(elt).text();
            step = step.replace(/^\d+\.\s+/, "");

            result.steps.push(step);
        });

        top.done(result);
    });
'''

        self.response.out.write(etree.tostring(tree))

app = webapp2.WSGIApplication([
        ('/', MainHandler),
        ('/api/scrape', ScrapeHandler)],
    debug=True)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

# vim: ts=4 sw=4
