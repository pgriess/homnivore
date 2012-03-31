from ..scrape import scrape
import unittest

class ScrapeTestCase(unittest.TestCase):
    def test_myrecipes_com(self):
        r = scrape(
            'http://www.myrecipes.com/recipe/beef-rendang-10000001963955/',
            'asdddddddddddddd')

        self.assertEqual('Beef Rendang', r.name)
        self.assertEqual('asdddddddddddddd', r.user_id)
        self.assertEqual(
            'http://www.myrecipes.com/recipe/beef-rendang-10000001963955/',
            r.url)
        self.assertEqual(18, len(r.ingredients))
        self.assertEqual('1/2 cup chopped shallots', r.ingredients[0])
        self.assertEqual(3, len(r.steps))
        self.assertTrue(r.steps[2].startswith('Heat a large saucepan'))
