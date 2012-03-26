import json
from ..models import Recipe
import unittest

class BaseModuleTestCase(unittest.TestCase):
    def test_to_json(self):
        expected = {
            'user_id': 'asdfasdfasdfas',
            'url': 'http://o234234.aafs.com/asdf',
            'name': '2094509234ldfasdf',
            'steps': [
                '131asdfasdfasdf',
                'lskddddddddddddddddddd']}

        recipe = Recipe( 
            user_id=expected['user_id'], url=expected['url'],
            name=expected['name'], steps=expected['steps'])
        actual = json.loads(recipe.to_json())

        self.assertDictContainsSubset(expected, actual)

    def test_from_json(self):
        expected = Recipe(
            user_id='lkjadsflkj13',
            url='http://2oi3r.ssssssss.co.in.uk.org.cc.xxx',
            name='alksjd',
            steps=[
                'alksdjflaksjdf',
                'asdfffffffffffffffffffff'])

        o = {
            'user_id': expected.user_id,
            'url': expected.url,
            'name': expected.name,
            'steps': expected.steps}

        actual = Recipe.from_json(json.dumps(o))

        # Use to_xml() to check equality because this is a method provided by
        # db.Model, so we trust that it's comprehensive. Theoretically, we
        # could use to_json() instead, but it seems safer to use this.
        self.assertEqual(expected.to_xml(), actual.to_xml())
