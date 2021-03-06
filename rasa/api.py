import requests
import json
import time
API_VERSION = 2.5
BASE_HEADER = {
    'accept': 'application/json',
    'content-type': 'application/json'
}


class TableauJSONAPI(object):


    def __init__(self, server_url = None, username = None, password = None, config_file = None):

        """
            Notes:
                self.post_sleep is the time allowed for post requests to process so that the index on tableau server
                can update, feel free to override, but may cause race conditions
        :param server_url:
        :param username:
        :param password:
        :param config_file:
        """
        self.post_sleep = 2

        if config_file is not None:
            self._set_from_config(config_file)
        else:
            self.server_url = server_url
            self.username = username
            self.password = password

        self.site_url = None
        self.site_id = None
        self.token = None

        self.auth_headers = None

        self.base_url  = "{server_url}/api/{api_version}".format(server_url=self.server_url, api_version=API_VERSION)

    def _set_from_config(self, path):

        data = json.load(open(path, 'rb'))
        self.server_url = data['server_url']
        self.username = data['username']
        self.password = data['password']


    def _get_json(self, url_route):
        url = self.base_url + url_route
        resp = requests.get(url, headers = self.auth_headers)
        resp.raise_for_status()
        return resp.json()

    def _post_json(self, url_route, payload):
        url = self.base_url + url_route
        resp = requests.post(url, headers = self.auth_headers, json=payload)
        resp.raise_for_status()
        print 'pausing', self.post_sleep, 'seconds to let index update'
        time.sleep(self.post_sleep)
        return resp.json()

    def _handle_post(self, route, payload, name):
        try:
            return self._post_json(route, payload=payload)
        except requests.HTTPError as e:
            if str(e).startswith('409'):
                print '{url} post: {name} Already Exists'.format(url=route, name=name)
            else:
                raise e

    def _clean_site_name(self, site_name):
        """
        pre processing of site name to Tableau Safe version
        :param site_name:
        :return:
        """
        return site_name.replace(' ', '')


    def auth_signin(self, site_url = ""):

        self.site_url = self._clean_site_name(site_url)

        url_path = self.base_url + '/auth/signin'

        payload = {'credentials':{
            'name': self.username,
            'password': self.password,
            'site': {
                'contentUrl': self.site_url
            }
        }}

        req = requests.post(url_path, json=payload, headers = BASE_HEADER)
        req.raise_for_status()
        resp = json.loads(req.content)

        self.token = resp['credentials']['token']
        self.site_id = resp['credentials']['site']['id']

        self.auth_headers = BASE_HEADER.copy()
        self.auth_headers['X-tableau-auth'] = self.token


        print('Sign in Successful to Site {site_url} {site_url_id}'.format(site_url = self.site_url, site_url_id = self.site_id))

        return self.token

    def auth_signout(self):

        url_path = self.base_url + '/auth/signout'

        req = requests.post(url_path, data = b'', headers = self.auth_headers)
        req.raise_for_status()

        print('Sign Out Successful')
        self.token = None
        self.auth_headers = None
        self.site_id = None
        self.site_url = None
        return None

    def auth_change_site(self, site_url=""):

        self.auth_signout()
        self.auth_signin(site_url)


    def sites_query_site(self, site_url = None):
        """
        :param site_url:
        :return:
        """
        if site_url:
            url_route = '/sites/{site_url}?key=contentUrl'.format(site_url = self._clean_site_name(site_url))
        else:
            url_route = '/sites/{site_id}'.format(site_id  = self.site_id)
        return self._get_json(url_route)


    def sites_query_sites(self):
        return self._get_json(url_route='/sites')


    def sites_query_views_for_site(self, include_usage_stats= False):

        get_usage_information = 'true' if include_usage_stats else 'false'
        url_route = '/sites/{site_id}/views?includeUsageStatistics={get_usage_information}'.format(
            site_id = self.site_id, get_usage_information = get_usage_information)
        return self._get_json(url_route)

    def workbooks_query_workbooks_for_sites(self, page_size = 1000, page_number = 1):
        url_route = '/sites/{site_id}/workbooks?pageSize={page_size}&pageNumber={page_number}'
        url_route = url_route.format(site_id=self.site_id, page_size=page_size, page_number=page_number)
        return self._get_json(url_route)

    def workbooks_query_workbooks_connections(self, workbook_id):
        url_route = '/sites/{site_id}/workbooks/{workbook_id}/connections'
        url_route = url_route.format(site_id=self.site_id, workbook_id=workbook_id)
        return self._get_json(url_route)

    def users_get_users_on_site(self, page_size = 1000, page_number = 1, as_id_lookup_table = False):
        url_route = '/sites/{site_id}/users?pageSize={page_size}&pageNumber={page_number}'
        url_route = url_route.format(site_id = self.site_id, page_size = page_size, page_number = page_number)
        resp = self._get_json(url_route)
        if as_id_lookup_table:
            return {user['name'].lower(): user['id'] for user in resp['users']['user']}
        return resp

    def users_query_user_on_site(self, user_id):
        url_route  = '/sites/{site_id}/users/{user_id}'.format(site_id = self.site_id, user_id = user_id)
        return self._get_json(url_route)

    def users_add_user_to_site(self, user_name, site_role = 'Interactor'):
        url_route = '/sites/{site_id}/users'.format(site_id=self.site_id)
        payload = {
            'user': {
                'name': user_name,
                'siteRole': site_role
            }
        }
        return self._handle_post(route=url_route, payload=payload, name=user_name)

    def groups_query_groups(self):
        url_route = '/sites/{site_id}/groups'.format(site_id = self.site_id)
        return self._get_json(url_route)

    def groups_create_group(self, group_name):
        url_route = '/sites/{site_id}/groups'.format(site_id = self.site_id)
        payload = {
            'group': {'name': group_name}
        }
        return self._handle_post(route=url_route, payload=payload, name=group_name)

    def groups_add_user_to_group(self, user_id, group_id):
        url_route = '/sites/{site_id}/groups/{group_id}/users'.format(site_id=self.site_id, group_id=group_id)
        payload = {
            'user': {'id': user_id}
        }
        return self._handle_post(route=url_route, payload=payload, name=user_id)

    def get_url(self, url):
        """
        makes an authenticated connection to the specifice url and returns the response object
        :param url:
        :return:
        """

        resp = requests.get(url, cookies = {"workgroup_session_id": self.token})
        resp.raise_for_status()
        return resp

    def get_group_id_from_groupname(self, group_name_list=[]):
        groups = self.groups_query_groups()['groups']['group']
        name_id_hash = {group['name'].lower(): group['id'] for group in groups}
        return [[group.lower(), name_id_hash.get(group.lower())] for group in group_name_list]

    def get_user_id_from_name(self, user_name_list=[]):

        user_id_hash = self.users_get_users_on_site(as_id_lookup_table=True)

        # preprocess un_list => lower username and pop from email if email is used
        pp_ = lambda un: un.lower().split('@')[0]
        return [[un, user_id_hash.get(un)] for un in map(pp_, user_name_list)]

    def script_batch_add_users_to_group(self, user_names=[], group_name=None, force = False):

        group_id = self.get_group_id_from_groupname(group_name_list=[group_name])[0][1]
        if not group_id:
            if force:
                self.groups_create_group(group_name)
            raise ValueError('Group %s Does Not Exist'%(str(group_name)))
        for un, uid in self.get_user_id_from_name(user_name_list=user_names):
            try:
                res = self.groups_add_user_to_group( uid, group_id)
                if res:
                    print 'Created Username', un, 'on Group', group_name
            except Exception as e:
                print e

    def script_get_workbooks_and_connections(self):
        site_users = self.users_get_users_on_site(as_id_lookup_table=True)
        id_to_name = {uid: un for un, uid in site_users.items()}
        workbooks = self.workbooks_query_workbooks_for_sites()
        print workbooks['pagination']['totalAvailable']

        table = []
        for workbook in workbooks['workbooks']['workbook']:
            # print workbook
            project, name, user_id = workbook['project']['name'], workbook['name'], workbook['owner']['id']
            print name
            for conn in self.workbooks_query_workbooks_connections(workbook['id'])['connections']['connection']:
                time.sleep(0.25)
                conn_name = conn['datasource']['name']
                server = conn['serverAddress']
                type_ = conn['type']
                user_name = conn['userName']
                table.append((project, name, id_to_name[user_id], conn_name, server, type_, user_name))
        return table

