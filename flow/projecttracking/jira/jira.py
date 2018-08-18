import datetime
import json
import os

import requests
from flow.buildconfig import BuildConfig
from flow.projecttracking.project_tracking_abc import Project_Tracking

import flow.utils.commons as commons
from flow.projecttracking.story import Story
from flow.utils.commons import Object


class Jira(Project_Tracking):

    clazz = 'Jira'
    token = None
    project_id = None
    jira_url = None
    config = BuildConfig
    http_timeout = 30

    def __init__(self, config_override=None):
        method = '__init__'
        commons.print_msg(Jira.clazz, method, 'begin')

        if config_override is not None:
            self.config = config_override

        # TODO: Put this back
        # Jira.token = os.getenv('JIRA_TOKEN')
        #
        # if not Jira.token:
        #     commons.print_msg(Jira.clazz, method, 'No tracker token found in environment.  Did you define '
        #                                             'environment variable \'JIRA_TOKEN\'?', 'ERROR')
        #     exit(1)

        try:
            # below line is to maintain backwards compatibility since stanza was renamed
            jira_json_config = self.config.json_config['jira'] if 'jira' in self.config.json_config else \
                                  self.config.json_config['projectTracking']["jira"]

            Jira.project_id = str(jira_json_config['projectId']).upper()
        except KeyError as e:
            commons.print_msg(Jira.clazz,
                              method,
                             "The build config associated with projectTracking is missing key {}".format(str(e)), 'ERROR')
            exit(1)

        # Check for tracker url first in buildConfig, second try settings.ini

        try:
            # noinspection PyUnboundLocalVariable
            Jira.jira_url = jira_json_config['url']
        except:
            if self.config.settings.has_section('jira') and self.config.settings.has_option('jira', 'url'):
                Jira.jira_url = self.config.settings.get('jira', 'url')
            else:
                commons.print_msg(Jira.clazz, method, 'No jira url found in buildConfig or settings.ini.', 'ERROR')
                exit(1)

    def get_details_for_all_stories(self, story_list):
        method = 'get_details_for_all_stories'
        commons.print_msg(Jira.clazz, method, 'begin')

        story_details = []

        for i, story_id in enumerate(story_list):
            story_detail = self._retrieve_story_detail(story_id)

            if story_detail is not None:
                story_details.append(story_detail)

        commons.print_msg(Jira.clazz, method, story_details)
        commons.print_msg(Jira.clazz, method, 'end')
        return story_details

    def _retrieve_story_detail(self, story_id):
        method = '_retrieve_story_detail'
        commons.print_msg(Jira.clazz, method, 'begin')

        jira_story_details_url = Jira.jira_url + '/rest/api/2/issue/' + story_id

        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

        commons.print_msg(Jira.clazz, method, jira_story_details_url)

        try:
            # TODO: Remove auth from below...
            resp = requests.get(jira_story_details_url, auth=("admin", "admin"), headers=headers,
                                timeout=self.http_timeout)
        except requests.ConnectionError:
            commons.print_msg(Jira.clazz, method, 'Request to Jira timed out.', 'ERROR')
            exit(1)
        except Exception as e:
            commons.print_msg(Jira.clazz, method, "Failed retrieving story detail from call to {} ".format(
                jira_story_details_url), 'WARN')
            commons.print_msg(Jira.clazz, method, e, 'ERROR')
            exit(1)

        json_data = None

        # noinspection PyUnboundLocalVariable
        if resp.status_code == 200:
            json_data = json.loads(resp.text)
            commons.print_msg(Jira.clazz, method, json_data)
            commons.print_msg(Jira.clazz, method, resp.text)

            story = Story()
            story.id = json_data.get('id')
            story.description = json_data.get('summary')
            story.url = Jira.jira_url + '/browse/' + json_data.get('key')
            story.name = json_data.get('key')
            story.story_type = json_data['fields']['issuetype']['name'].lower()
            story.labels = json_data['fields']['labels']
            story.versions = []
            for version in json_data['fields']['fixVersions']:
                story.versions.append(version["name"])

        else:
            commons.print_msg(Jira.clazz, method, "Failed retrieving story detail from call to {url}. \r\n "
                                                    "Response: {response}".format(url=jira_story_details_url,
                                                                                  response=resp.text), 'WARN')

        commons.print_msg(Jira.clazz, method, 'end')

        return story

    def tag_stories_in_commit(self, story_list):
        method = 'tag_stories_in_commit'
        commons.print_msg(Jira.clazz, method, 'begin')

        for story in story_list:
            label = self.config.project_name + '-' + self.config.version_number

            self._add_version_to_jira_story(story, label)

        commons.print_msg(Jira.clazz, method, 'end')

    def _create_version(self, version, released=False):
        method = '_create_version'
        commons.print_msg(Jira.clazz, method, 'begin')

        new_version = Object()
        new_version.description = "Generated from pipeline"
        new_version.name = version
        if released:
            new_version.userReleaseDate = datetime.datetime.now().strftime("%-d/%b/%Y")
        new_version.project = Jira.project_id
        new_version.released = released

        jira_url = "{}/rest/api/2/version".format(Jira.jira_url)

        headers = {'Content-type': 'application/json'}

        commons.print_msg(Jira.clazz, method, jira_url)
        commons.print_msg(Jira.clazz, method, new_version.to_JSON())

        try:
            # TODO: Remove auth from below...
            resp = requests.post(jira_url, new_version.to_JSON(), headers=headers, auth=('admin', 'admin'), timeout=self.http_timeout)

            if resp.status_code != 201:
                commons.print_msg(Jira.clazz, method, "Unable to add version {version} \r\n "
                                                      "Response: {response}".format(version=version, response=resp.text)
                                  , 'WARN')
            else:
                commons.print_msg(Jira.clazz, method, resp.text)
        except requests.ConnectionError as e:
            commons.print_msg(Jira.clazz, method, 'Connection error. ' + str(e), 'WARN')
        except Exception as e:
            commons.print_msg(Jira.clazz, method, "Unable to add version {verions}".format(version=version), 'WARN')
            commons.print_msg(Jira.clazz, method, e, 'WARN')

        commons.print_msg(Jira.clazz, method, 'end')

    def _add_version_to_jira_story(self, story_id, label):
        method = '_add_version_to_jira_story'
        commons.print_msg(Jira.clazz, method, 'begin')

        detail = self._retrieve_story_detail(story_id)

        versions = detail.versions
        versions.append(label)

        self._create_version(self.config.project_name + '-' + self.config.version_number)

        add_version_story = Object()
        add_version_story.update = Object()
        add_version_story.update.fixVersions = []
        set_version = Object()
        set_version.set = []
        for current_version in versions:
            version = Object()
            version.name = current_version
            set_version.set.append(version)
        add_version_story.update.fixVersions.append(set_version)

        jira_url = "{url}/rest/api/2/issue/{storyid}".format(url=Jira.jira_url, storyid=story_id)

        headers = {'Content-type': 'application/json', 'Accept': 'application/json'}

        commons.print_msg(Jira.clazz, method, jira_url)
        commons.print_msg(Jira.clazz, method, add_version_story.to_JSON())

        try:
            # TODO: Remove auth from below...
            resp = requests.put(jira_url, add_version_story.to_JSON(), auth=("admin", "admin"), headers=headers, timeout=self.http_timeout)

            if resp.status_code != 204:
                commons.print_msg(Jira.clazz, method, "Unable to tag story {story} with label {lbl} \r\n "
                                                         "Response: {response}".format(story=story_id, lbl=label,
                                                                                       response=resp.text), 'WARN')
            else:
                commons.print_msg(Jira.clazz, method, resp.text)
        except requests.ConnectionError as e:
            commons.print_msg(Jira.clazz, method, 'Connection error. ' + str(e), 'WARN')
        except Exception as e:
            commons.print_msg(Jira.clazz, method, "Unable to tag story {story} with label {lbl}".format(
                story=story_id, lbl=label), 'WARN')
            commons.print_msg(Jira.clazz, method, e, 'WARN')

        commons.print_msg(Jira.clazz, method, 'end')

    def determine_semantic_version_bump(self, story_details):
        method = 'determine_semantic_version_bump'
        commons.print_msg(Jira.clazz, method, 'begin')

        bump_type = None

        for i, story in enumerate(story_details):
            for j, label in story.labels:
                if label.get('name') == 'major':
                    return 'major'

            if story.story_type == story:
                bump_type = 'minor'
            elif story.story_type == 'bug' and bump_type is None:
                bump_type = 'bug'

        # This fall-through rule is needed because if there are no tracker
        # stories present in the commits, we need to default to something,
        # else calculate_next_semver will throw an error about getting 'None'
        if bump_type is None:
            bump_type = 'minor'

        commons.print_msg(Jira.clazz, method, "bump type: {}".format(bump_type))

        commons.print_msg(Jira.clazz, method, 'end')

        return bump_type
