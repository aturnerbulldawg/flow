import json
import requests
import flow.utils.commons as commons
from flow.buildconfig import BuildConfig
from flow.utils.commons import Object
import os

class ServiceNow():

    clazz = 'ServiceNow'
    servicenow_url = None
    config = BuildConfig

    def __init__(self, config_override=None):
        method = '__init__'
        commons.print_msg(ServiceNow.clazz, method, 'begin')

        if config_override is not None:
            self.config = config_override

        try:
            # below line is to maintain backwards compatibility since stanza was renamed
            servicenow_json_config = self.config.json_config['servicenow'] if 'servicenow' in self.config.json_config else \
                                  self.config.json_config['servicemanagement']["servicenow"]
        except KeyError as e:
            commons.print_msg(ServiceNow.clazz,
                              method,
                             "The build config associated with servicemanagement is missing key {}".format(str(e)), 'ERROR')
            exit(1)

        # Check for servicenow url first in buildConfig, second try settings.ini
        try:
            # noinspection PyUnboundLocalVariable
            ServiceNow.servicenow_url = servicenow_json_config['url']
        except:
            if self.config.settings.has_section('servicenow') and self.config.settings.has_option('servicenow', 'url'):
                ServiceNow.servicenow_url = self.config.settings.get('servicenow', 'url')
            else:
                commons.print_msg(ServiceNow.clazz, method, 'No service now url found in buildConfig or settings.ini.', 'ERROR')
                exit(1)

    def create_chg(self):
        servicenow_create_chg_url = ServiceNow.servicenow_url + '/api/now/table/change_request'

        cr = Object()
        cr.reason = 'Continuous Deployment'
        headers = {'Content-type': 'application/json', 'Accept': 'application/json',
                   'Authorization': "Bearer {}".format(os.getenv('SERVICENOW_TOKEN'))}

        print(servicenow_create_chg_url)
        resp = requests.post(servicenow_create_chg_url, cr.to_JSON(), headers=headers)
        resp_obj = json.loads(resp.text)
        print(resp)
        print(resp.text)
        print(resp_obj["result"]["number"])
