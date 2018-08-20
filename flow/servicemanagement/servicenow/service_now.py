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

    def create_chg(self, story_details = None):
        servicenow_create_chg_url = ServiceNow.servicenow_url + '/api/now/table/change_request'

        cr = Object()
        cr.category = "Software"
        cr.description = self._format_release_notes(story_details)
        cr.short_description = "Automated Deploy of {app}-{version} to {env}".format(app=BuildConfig.project_name, version=BuildConfig.version_number, env=BuildConfig.build_env)
        cr.assignment_group = 'CAB Approval'
        cr.work_start = '2018-08-10 23:59:59'
        cr.work_end = '2018-08-11 23:59:59'
        cr.cmdb_ci = 'Cloud Foundry'
        cr.start_date = '2018-08-10 23:59:59'
        cr.end_date = '2018-08-11 23:59:59'
        cr.reason = 'Continuous Deployment'
        # headers = {'Content-type': 'application/json', 'Accept': 'application/json',
        #            'Authorization': "Bearer {}".format(os.getenv('SERVICENOW_TOKEN'))}

        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

        print(servicenow_create_chg_url)
        resp = requests.post(servicenow_create_chg_url, cr.to_JSON(), headers=headers, auth=(os.getenv('SERVICENOW_USER'), os.getenv('SERVICENOW_PWD')),)
        resp_obj = json.loads(resp.text)
        print(resp)
        print(resp.text)
        print(resp_obj["result"]["number"])

    def _format_release_notes(self, story_details):

        formatted_release_notes = None

        if story_details is not None and isinstance(story_details, list) and len(story_details) > 0:

            for i, story in enumerate(story_details):
                if story is not None:

                    if formatted_release_notes is None:
                        formatted_release_notes = "======================================RELEASE NOTES======================================"
                        formatted_release_notes = formatted_release_notes + "\r\n=========================================from Jira========================================="

                    formatted_release_notes = "{existing} \r\n {counter}. ({type}) {name} => {description}".format(existing=formatted_release_notes, counter=i+1, type=story.story_type, name=story.name, description=story.description)

        if formatted_release_notes is None:
            formatted_release_notes = 'No Release Notes'

        return formatted_release_notes
