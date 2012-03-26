'''
Data model classes.

These have a dependency on Google App Engine, but could theoretically be ported
to some other ORM. They also provide some extensions to the base Model
functionality like serialization to/from JSON.
'''

import datetime
from google.appengine.ext import db
import json
import time

# A base class to provide to/from JSON serialization.
#
# The serialization code is almost a direct quote of
#
#   http://stackoverflow.com/questions/1531501/json-serialization-of-google-app-engine-models
class _BaseModel(db.Model):

    # Set of types that do not require explicit conversion
    _SIMPLE_TYPES = (int, long, float, bool, dict, basestring, list)

    def to_json(self):
        '''
        Serialize a Model object to JSON.
        '''

        o = {}

        for name, prop in self.properties().iteritems():
            val = getattr(self, name)

            if val is None or isinstance(val, _BaseModel._SIMPLE_TYPES):
                o[name] = val
            elif isinstance(val, datetime.date):
                ms = time.mktime(val.utctimetuple())
                ms += getattr(val, 'microseconds', 0) / 1000
                o[name] = int(ms)
            elif isinstance(val, db.GeoPt):
                o[name] = {'lat': val.lat, 'lon': val.lon}
            elif isinstance(val, db.Model):
                o[name] = _BaseModel.to_json(val)
            else:
                raise ValueError('cannot encode ' + repr(prop))

        return json.dumps(o)


    @classmethod
    def from_json(cls, json_str):
        '''
        De-serialize a Model object from a JSON string.
        '''

        o = json.loads(json_str)
        if not isinstance(o, dict):
            raise ValueError('JSON object was not a dictionary')

        # Populate the set of keyword arguments that we'll use to create the
        # instance. We have to do this because the db.Model class enforces
        # required properties at construction time
        kwargs = {}
        props = cls.properties()

        for name, val in o.iteritems():
            # Ignore unexpected items
            if not name in props:
                continue

            prop = props[name]

            if isinstance(val, prop.data_type):
                kwargs[name] = val
            else:
                raise ValueError('cannot decode ' + repr(val))

        return cls(**kwargs)


class Recipe(_BaseModel):
    user_id = db.StringProperty(required=True)
    url = db.StringProperty(required=True)
    name = db.StringProperty(required=True)
    ingredients = db.StringListProperty(required=True)
    steps = db.StringListProperty(required=True)
    image = db.StringProperty(required=False)
