# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os
import json
import unittest
import requests

from pymongo import MongoClient

from minion.backend.api import BUILTIN_PLUGINS, TEST_PLUGINS

BASE = 'http://localhost:8383'
APIS = {'user':
            {'POST': '/users',
             'GET': '/users'},
        'groups':
            {'POST': '/groups',
              'GET': '/groups'},
        'group':
            {'GET': '/groups/{group_name}',
             'DELETE': '/groups/{group_name}',
             'PATCH': '/groups/{group_name}'},
        'get_plans': 
            {'GET': '/plans'},
        'get_plan':
            {'GET': '/plans/{plan_name}'},
        'get_plugins':
            {'GET': '/plugins'},
}

def get_api(api_name, method, args=None):
    """ Return a full url and map each key
    in args to the url found in APIS. """
    api = ''.join([BASE, APIS[api_name][method]])
    if args:
        return api.format(**args)
    else:
        return api

def _call(task, method, auth=None, data=None, url_args=None):
    """
    Make HTTP request.

    Parameters
    ----------
    task : str
        The name of the api to call which corresponds
        to a key name in ``APIS``.
    method : str
        Accept 'GET', 'POST', 'PUT', or
        'DELETE'.
    auth : optional, tuple
        Basic auth tuple ``(username, password)`` pair.
    data : optional, dict
        A dictionary of data to pass to the API.
    url_args : optional, dict
        A dictionary of url arguments to replace in the 
        URL. For example, to match user's GET URL which
        requires ``id``, you'd pass ``{'id': '3a7a67'}``.

    Returns
    -------
    res : requests.Response
        The response object.
    
    """

    req_objs = {'GET': requests.get,
        'POST': requests.post,
        'PUT': requests.put,
        'DELETE': requests.delete,
        'PATCH': requests.patch}

    method = method.upper()
    api = APIS[task][method]
    if url_args:
        api = api.format(**url_args)
    # concatenate base and api
    api = os.path.join(BASE.strip('/'), api.strip('/'))

    headers = {'Content-Type': 'application/json'}
    req_objs = req_objs[method]
    data = json.dumps(data)

    if method == 'GET' or method == 'DELETE':
        res = req_objs(api, params=data, auth=auth, headers=headers)
    else:
        res = req_objs(api, data=data, auth=auth, headers=headers)
    return res

class TestAPIBaseClass(unittest.TestCase):
    def setUp(self):
        self.mongodb = MongoClient()
        self.mongodb.drop_database("minion")
        self.db = self.mongodb.minion

        self.email = "bob@example.org"
        self.email2 = "alice@example.org"
        self.role = "user"
        self.group_name = "minion-test-group"
        self.group_description = "minion test group is awesome."
        
        self.add_site = "http://foo.com"
        self.remove_site = "http://bar.com"

    def tearDown(self):
        self.mongodb.drop_database("minion")

    def create_user(self):
        return _call('user', 'POST', data={"email": self.email, "role": "user"})
    
    def get_users(self):
        return _call('user', 'GET')

    def create_group(self):
        return _call('groups', 'POST', data={'name': self.group_name, 
            "description": self.group_description})

    def get_groups(self):
        return _call('groups', 'GET')

    def get_group(self, group_name):
        return _call('group', 'GET', url_args={'group_name': group_name})

    def delete_group(self, group_name):
        return _call('group', 'DELETE', url_args={'group_name': group_name})

    def modify_group(self, group_name, data=None):
        return _call('group', 'PATCH', url_args={'group_name': group_name},
                data=data)

    def _test_keys(self, target, expected):
        """
        Compare keys are in the response. If there
        is a difference (more or fewer) assertion
        will raise False.
        
        Parameters
        ----------
        target : tuple
            A tuple of keys from res.json().keys()
        expected : tuple
            A tuple of keys expecting to match
            against res.json().keys()

        """

        keys1 = set(expected)
        self.assertEqual(set(), keys1.difference(target))

class TestUserAPIs(TestAPIBaseClass):
    def test_create_user(self):
        res = self.create_user() 
        expected_top_keys = ('user', 'success')
        self._test_keys(res.json().keys(), expected_top_keys)
        expected_inner_keys = ('id', 'created', 'role', 'email')
        self._test_keys(res.json()['user'].keys(), expected_inner_keys)

    def test_get_all_users(self):
        # we must recreate user
        self.create_user()
        res = self.get_users()
        expected_inner_keys = ('id', 'email', 'role', 'sites', 'groups')
        self._test_keys(res.json()['users'][0].keys(), expected_inner_keys)
        self.assertEqual(1, len(res.json()['users']))

class TestGroupAPIs(TestAPIBaseClass):
    def test_create_group(self):
        res = self.create_user()
        res = self.create_group()
        expected_top_keys = ('success', 'group')
        self._test_keys(res.json().keys(), expected_top_keys)
        expected_inner_keys = ('id', 'created', 'name', 'description')
        self._test_keys(res.json()['group'], expected_inner_keys)
        self.assertEqual(res.json()['group']['name'], self.group_name)
        self.assertEqual(res.json()['group']['description'], self.group_description)

    def test_create_duplicate_group(self):
        res = self.create_user()
        res = self.create_group()
        res = self.create_group()
        expected_top_keys = ('success', 'reason')
        self._test_keys(res.json().keys(), expected_top_keys)
        self.assertEqual(res.json()['success'], False)
        self.assertEqual(res.json()['reason'], 'group-already-exists')

    def test_get_all_groups(self):
        res = self.create_user()
        res1 = self.create_group()
        res2 = self.get_groups()
        expected_top_keys = ('success', 'groups')
        self._test_keys(res2.json().keys(), expected_top_keys)
        self.assertEqual(res2.json()['groups'][0], res1.json()['group'])

    def test_get_group(self):
        res = self.create_user()
        res1 = self.create_group()
        res2 = self.get_group(self.group_name)
        expected_top_keys = ('success', 'group')
        self._test_keys(res2.json().keys(), expected_top_keys)
        self.assertEqual(res2.json()['group']['name'], self.group_name)
        self.assertEqual(res2.json()['group']['description'], self.group_description)

    def test_delete_group(self):
        res = self.create_user()
        res1 = self.create_group()
        res2 = self.delete_group(self.group_name)
        expected_top_keys = ('success', )
        self._test_keys(res2.json().keys(), expected_top_keys)
        self.assertEqual(res2.json()['success'], True)

    def test_patch_group_add_site(self):
        res = self.create_user()
        res1 = self.create_group()
        res2 = self.modify_group(self.group_name,
                data={'addSites': [self.add_site]})
        self._test_keys(res2.json().keys(), set(res1.json().keys()))
        self._test_keys(res2.json()['group'].keys(), set(res1.json()['group'].keys()))
        self.assertEqual(res2.json()['group']['sites'][0], self.add_site)

    def test_patch_group_remove_site(self):
        res = self.create_user()
        res1 = self.create_group()
        res2 = self.modify_group(self.group_name,
                data={'addSites': [self.remove_site]})
        self.assertEqual(res2.json()['group']['sites'][0], self.remove_site)

        res2 = self.modify_group(self.group_name,
                data={'removeSites': [self.remove_site]})
        self._test_keys(res2.json().keys(), set(res1.json().keys()))
        self._test_keys(res2.json()['group'].keys(), set(res1.json()['group'].keys()))
        self.assertEqual(res2.json()['group']['sites'], [])

    def test_patch_group_add_user(self):
        res = self.create_user()
        res1 = self.create_group()
        res2 = self.modify_group(self.group_name,
                data={'addUsers': [self.email2]})
        self._test_keys(res2.json().keys(), set(res1.json().keys()))
        self._test_keys(res2.json()['group'].keys(), set(res1.json()['group'].keys()))
        self.assertEqual(res2.json()['group']['users'][0], self.email2)

    def test_patch_group_remove_user(self):
        res = self.create_user()
        res1 = self.create_group()
        res2 = self.modify_group(self.group_name,
                data={'addUsers': [self.email2]})
        self.assertEqual(res2.json()['group']['users'][0], self.email2)

        res2 = self.modify_group(self.group_name,
                data={'removeUsers': [self.email2]})
        self._test_keys(res2.json().keys(), set(res1.json().keys()))
        self._test_keys(res2.json()['group'].keys(), set(res1.json()['group'].keys()))
        self.assertEqual(res2.json()['group']['users'], [])

class TestBackendAPIs(unittest.TestCase):
    def setUp(self):
        ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        PLANS_ROOT = os.path.join(ROOT, 'plans')

        self.mongodb = MongoClient()
        self.db = self.mongodb.minion
        self.plans = self.db.plans
        self.scans = self.db.scans
        with open(os.path.join(PLANS_ROOT, 'basic.plan'), 'r') as f:
            self.plan = json.load(f)
            self.plans.remove({'name': self.plan['name']})
            self.plans.insert(self.plan)
    
    @staticmethod
    def _get_plugin_name(full):
        """ Return the name of the plugin. """
        cls_name = full.split('.')[-1]
        return cls_name.split('Plugin')[0]

    def test_get_plans(self):
        API = get_api('get_plans', 'GET')
        expected = {
            u"plans": 
            [
                {
                    u"description": u"Run basic tests", 
                    u"name": u"basic"
                }
            ],
            u"success": True
        }
        resp = requests.get(API)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(expected, resp.json())

    @staticmethod
    def _check_plugin_metadata(tself, base, metadata):
        """ Given a base configuration, parse
        and verify the input metadata contains
        the following keys: 'version', 'class',
        'weight', and 'name' for each plugin. """

        for index, plugin in enumerate(metadata):
            p_name = tself._get_plugin_name(base['workflow'][index]['plugin_name'])
            # the plugin list is either under the key plugin, plugins or
            # itself is already a list. We should consider using plugins
            # over plugin; that is, change the key name in /plugins endpoint.
            meta = plugin.get('plugin') or plugin.get('plugins') or plugin
            tself.assertEqual('light', meta['weight'])
            tself.assertEqual(p_name, meta['name'])
            tself.assertEqual(base['workflow'][index]['plugin_name'], meta['class'])
            tself.assertEqual("0.0", meta['version'])
    
    def test_get_plan(self):
        API = get_api('get_plan', 'GET', args={'plan_name': 'basic'})
        resp = requests.get(API)
        self.assertEqual(200, resp.status_code)

        # test plugin name and weight. weight is now always light for the built-in
        plan = resp.json()
        self._check_plugin_metadata(self, self.plan, plan['plan']['workflow'])
    
    def test_get_built_in_plugins(self):
        API = get_api('get_plugins', 'GET')
        resp = requests.get(API)
        self.assertEqual(200, resp.status_code)
        # check top-leve keys agreement
        self.assertEqual(True, 'plugins' in resp.json().keys())
        self.assertEqual(True, 'success' in resp.json().keys())
        # num of total built-in plugins should match
        plugins_count = len(TEST_PLUGINS) + len(BUILTIN_PLUGINS)
        self.assertEqual(plugins_count, len(resp.json()['plugins']))
        # check following keys are returned for each plugin
        for plugin in resp.json()['plugins']:
            self.assertEqual(['class', 'name', 'version', 'weight'],
                sorted(plugin.keys()))
        #TODO: Need to fix this last part of the test.
        # Apparently the plugins within the plugins list is not oredered
        # like the one returned from get_plans or get_plan. Robots comes
        # first before Alive.
        # check plugin name, weight, class, version
        # self._check_plugin_metadata(self, self.plan, resp.json()['plugins'])
