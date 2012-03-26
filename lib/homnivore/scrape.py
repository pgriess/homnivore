'''
Scaping utilities.
'''

from lxml import etree
from .models import Recipe
import re
import urllib2
from urlparse import urlsplit


###############################################################################
# Scraper functions; one per domain
#
# Each method returns a fully populated Recipe object based on the provided
# lxml tree object and the extra keyword arguments, the latter of which should
# be passed to the Recipe constructor.
###############################################################################
def __www_myrecipes_com_scraper(tree, **kwargs):
    name = tree.xpath('//head/title')[0].text
    name = name[:len(name) - len(' Recipe | MyRecipes.com')]

    ingredients = []
    for e in tree.xpath('//li[@itemprop="ingredient"]'):
        ingredient = \
            e.xpath('span[@itemprop="amount"]')[0].text + ' ' + \
            e.xpath('span[@itemprop="name"]')[0].text + ' ' + \
            e.xpath('span[@itemprop="preparation"]')[0].text
        ingredient = ingredient.strip()
        ingredient = re.sub(r'\s+', ' ', ingredient)

        ingredients += [ingredient]

    steps = []
    for e in tree.xpath('//ol[@itemprop="instructions"]/li'):
        steps += [re.sub(r'^\d+\.\s+', '', e.text, flags=re.UNICODE)]

    image = None
    for e in tree.xpath('//img[@alt="%s Recipe"]' % name):
        image = e.attrib['src']

    return Recipe(
        name=name, ingredients=ingredients, steps=steps, image=image,
        **kwargs)


# Map of hostnames to scraper functions
__SCRAPER_MAP = {
    'www.myrecipes.com': __www_myrecipes_com_scraper}


def scrape(url, user_id):
    '''
    Scrape a Recipe from the given URL on behalf of the given user.

    Returns None if no recipe could be scraped (e.g. because no scraper could
    be found for the specified URL).
    '''

    url_components = urlsplit(url)

    scraper = __SCRAPER_MAP.get(url_components.hostname, None)
    if not scraper:
        return None

    # Fetch the URL and construct an LXML tree
    result = urllib2.urlopen(url)
    parser = etree.HTMLParser()
    tree = etree.parse(result, parser)

    # Construct a Recipe object and fill it out using the scraper
    kwargs = {
        'url': url,
        'user_id': user_id}

    return scraper(tree, **kwargs)
