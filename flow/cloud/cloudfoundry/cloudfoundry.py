import os
import subprocess
import tarfile
import urllib.request
import requests
import json

import logging, http.client as http_client

from subprocess import TimeoutExpired
import platform

from flow.buildconfig import BuildConfig
from flow.cloud.cloud_abc import Cloud
from requests.auth import HTTPBasicAuth
import flow.utils.commons as commons
from flow.utils.commons import Object


class CloudFoundry(Cloud):

    clazz = 'CloudFoundry'
    cf_org = None
    cf_space = None
    cf_api_endpoint = None
    cf_domain = None
    cf_user = None
    cf_pwd = None
    path_to_cf = None
    stopped_apps = None
    started_apps = None
    config = BuildConfig
    http_timeout = 30
    api_token = None
    space_guid = None
    cf_api_login_endpoint = None


    def __init__(self, config_override=None):
        method = '__init__'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        if config_override is not None:
            self.config = config_override

        CloudFoundry.path_to_cf = ""

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def api_login(self):
        method = '_api_login'

        #TODO Remove this
        CloudFoundry.cf_api_login_endpoint = 'login.sys.fog.onefiserv.net'

        self._verify_required_attributes()

        payload = {'grant_type': 'password', 'password': CloudFoundry.cf_pwd,
                   'username': CloudFoundry.cf_user}

        pcf_login_headers = {'Content-type': 'application/x-www-form-urlencoded',
                             'Host': CloudFoundry.cf_api_login_endpoint, 'username': CloudFoundry.cf_user}

        login_url = "https://{}/oauth/token".format(CloudFoundry.cf_api_login_endpoint)

        try:
            resp = requests.post(login_url, auth=HTTPBasicAuth('cf', ''), params=payload,
                                 headers=pcf_login_headers, verify=False)
            json_data = json.loads(resp.text)

            CloudFoundry.api_token = json_data['access_token']
        except requests.ConnectionError:
                commons.print_msg(CloudFoundry.clazz, method, 'Request to Cloud Foundry timed out.', 'ERROR')
                exit(1)
        except:
            commons.print_msg(CloudFoundry.clazz, method, "The cloud foundry api login call to {} has failed".
                              format(CloudFoundry.cf_api_login_endpoint), 'ERROR')
            exit(1)

        if CloudFoundry.api_token is None:
            commons.print_msg(CloudFoundry.clazz, method, 'Failed to find API token', 'ERROR')
            exit(1)

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def download_cf_cli(self):
        method = '_download_cf_cli'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        cmd = "where" if platform.system() == "Windows" else "which"
        rtn = subprocess.call([cmd, 'cf'])

        if rtn == 0:
            commons.print_msg(CloudFoundry.clazz, method, 'cf cli already installed')
        else:
            commons.print_msg(CloudFoundry.clazz, method, "cf CLI was not installed on this image. "
                                                        "Downloading CF CLI from {}".format(
                self.config.settings.get('cloudfoundry', 'cli_download_path')))

            urllib.request.urlretrieve(self.config.settings.get('cloudfoundry', 'cli_download_path'), # nosec
                                           './cf-linux-amd64.tgz')
            tar = tarfile.open('./cf-linux-amd64.tgz')
            CloudFoundry.path_to_cf = "./"
            tar.extractall()
            tar.close()

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _get_space_guid(self):
        method = '_get_space_guid'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        bearer_token = "bearer {access_token}".format(access_token=CloudFoundry.api_token)

        pcf_spaces_headers = {'Authorization': bearer_token}

        spaces_url = "https://{api}/v2/spaces".format(api=CloudFoundry.cf_api_endpoint)

        try:
            resp = requests.get(spaces_url, headers=pcf_spaces_headers, verify=False)
        except requests.ConnectionError:
            commons.print_msg(CloudFoundry.clazz, method, 'Request to Cloud Foundry timed out.', 'ERROR')
            exit(1)
        except:
            commons.print_msg(CloudFoundry.clazz, method, "The cloud foundry api get spaces call failed. {}".
                              format(spaces_url), 'ERROR')
            exit(1)

        json_data = json.loads(resp.text)

        # Since this URL gets all spaces, we are looking only for the one that we need
        for i, app in enumerate(json_data['resources']):
            if app['entity']['name'] in CloudFoundry.cf_space:
                CloudFoundry.space_guid = app['metadata']['guid']
                break

        if CloudFoundry.space_guid is None:
            commons.print_msg(CloudFoundry.clazz, method, 'Failed to find space', 'ERROR')
            exit(1)

        commons.print_msg(CloudFoundry.clazz, method, "space guid is {}".format(CloudFoundry.space_guid))

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _verify_required_attributes(self):
        method = '_verify_required_attributes'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        commons.print_msg(CloudFoundry.clazz, method, "workspace {}".format(CloudFoundry.path_to_cf))

        if os.environ.get('DEPLOYMENT_USER') is None:
            commons.print_msg(CloudFoundry.clazz, method, "No User Id. Did you forget to define environment variable "
                                                         "'DEPLOYMENT_USER?", 'ERROR')
            exit(1)
        else:
            CloudFoundry.cf_user = os.environ.get('DEPLOYMENT_USER')

        if os.environ.get('DEPLOYMENT_PWD') is None:
            commons.print_msg(CloudFoundry.clazz, method, "No User Password. Did you forget to define environment "
                                                         "variable 'DEPLOYMENT_PWD'?", 'ERROR')
            exit(1)
        else:
            CloudFoundry.cf_pwd = os.environ.get('DEPLOYMENT_PWD')

        try:
            # noinspection PyStatementEffect
            self.config.json_config['projectInfo']['name']
            CloudFoundry.cf_org = self.config.build_env_info['cf']['org']
            CloudFoundry.cf_space = self.config.build_env_info['cf']['space']
            CloudFoundry.cf_api_endpoint = self.config.build_env_info['cf']['apiEndpoint']
            if 'domain' in self.config.build_env_info['cf']:  # this is not required bc could be passed in via manifest
                CloudFoundry.cf_domain = self.config.build_env_info['cf']['domain']

            commons.print_msg(CloudFoundry.clazz, method, "CloudFoundry.cf_org {}".format(CloudFoundry.cf_org))
            commons.print_msg(CloudFoundry.clazz, method, "CloudFoundry.cf_space {}".format(CloudFoundry.cf_space))
            commons.print_msg(CloudFoundry.clazz, method, "CloudFoundry.cf_api_endpoint {}"
                              .format(CloudFoundry.cf_api_endpoint))
            commons.print_msg(CloudFoundry.clazz, method, "CloudFoundry.cf_domain {}".format(CloudFoundry.cf_domain))
        except KeyError as e:
            commons.print_msg(CloudFoundry.clazz,
                              method,
                             "The build config associated with cloudfoundry is missing key {}".format(str(e)), 'ERROR')
            exit(1)

    def _check_cf_version(self):
        method = '_check_cf_version'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        cmd = "{}cf --version".format(CloudFoundry.path_to_cf)
        cf_version = subprocess.Popen(cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        try:
            cf_version_output, errs = cf_version.communicate(timeout=120)

            for line in cf_version_output.splitlines():
                commons.print_msg(CloudFoundry.clazz, method, line.decode('utf-8'))

            if cf_version.returncode != 0:
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}".format(
                    command=cmd, rtn=cf_version.returncode), 'ERROR')

                os.system('stty sane')
                self._cf_logout()
                exit(1)

        except TimeoutExpired:
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd), 'ERROR')
            cf_version.kill()
            os.system('stty sane')
            self._cf_logout()
            exit(1)

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _get_stopped_apps(self):
        method = '_get_stopped_apps'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        bearer_token = "bearer {access_token}".format(access_token=self.api_token)

        pcf_apps_headers = {'Authorization': bearer_token}

        apps_url = "https://{api}/v2/spaces/{space_guid}/apps".format(api=CloudFoundry.cf_api_endpoint,
                                                                      space_guid=CloudFoundry.space_guid)

        commons.print_msg(CloudFoundry.clazz, method, apps_url)
        stopped_apps = []

        try:
            resp = requests.get(apps_url, headers=pcf_apps_headers, verify=False)
        except requests.ConnectionError:
            commons.print_msg(CloudFoundry.clazz, method, 'Request to Cloud Foundry timed out.', 'ERROR')
            exit(1)
        except:
            commons.print_msg(CloudFoundry.clazz, method, "The cloud foundry get stopped apps has failed {}".
                              format(apps_url), 'ERROR')
            exit(1)

        json_data = json.loads(resp.text)
        
        for i, app in enumerate(json_data['resources']):
            if app['entity']['name'].lower().startswith("{}-".format(self.config.project_name.lower())) \
                    and app['entity']['state'].lower() == 'stopped':
                app_obj = Object()
                app_obj.name = app['entity']['name']
                app_obj.guid = app['metadata']['guid']
                stopped_apps.append(app_obj)

        commons.print_msg(CloudFoundry.clazz, method, "found {} stopped apps".format(len(stopped_apps)))

        CloudFoundry.stopped_apps = stopped_apps

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    # sets list of started applications
    # additionally, if the version being deployed is found and already started, it either
    #    - warns the user that zero-downtime cannot occur (if force_deploy is True) OR
    #    - errors to the user that it cannot continue with zero downtime (if force_deploy is False)
    def _get_started_apps(self, force_deploy=False):
        method = '_get_started_apps'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        bearer_token = "bearer {access_token}".format(access_token=self.api_token)

        pcf_apps_headers = {'Authorization': bearer_token}

        apps_url = "https://{api}/v2/spaces/{space_guid}/apps".format(api=CloudFoundry.cf_api_endpoint,
                                                                      space_guid=CloudFoundry.space_guid)
        started_apps = []

        version_to_look_for = "{proj}-{ver}".format(proj=self.config.project_name.lower(), ver=self.config.version_number)

        try:
            resp = requests.get(apps_url, headers=pcf_apps_headers, verify=False)
        except requests.ConnectionError:
            commons.print_msg(CloudFoundry.clazz, method, 'Request to Cloud Foundry timed out.', 'ERROR')
            self._cf_logout()
            exit(1)
        except:
            commons.print_msg(CloudFoundry.clazz, method, "The cloud foundry api login call failed to {} has failed".
                              format(apps_url), 'ERROR')
            self._cf_logout()
            exit(1)

        json_data = json.loads(resp.text)

        for i, app in enumerate(json_data['resources']):
            if app['entity']['name'].lower().startswith("{}-".format(self.config.project_name.lower())) \
                    and app['entity']['state'].lower() == 'started':
                app_obj = Object()
                app_obj.name = app['entity']['name']
                app_obj.guid = app['metadata']['guid']
                started_apps.append(app_obj)

        for i, started_app in enumerate(started_apps):
            if started_app.name.lower() == version_to_look_for and not force_deploy:
                commons.print_msg(CloudFoundry.clazz, method, "App version {} already exists and is running. "
                                                              "Cannot perform zero-downtime deployment.  To "
                                                              "override, set force flag = 'true'".format(
                    version_to_look_for), 'ERROR')

                self._cf_logout()
                exit(1)

            elif started_app.name.lower() == version_to_look_for and force_deploy:
                commons.print_msg(CloudFoundry.clazz, method, "Already found {} but force_deploy turned on. "
                                                              "Continuing with deployment.  Downtime will occur "
                                                              "during deployment.".format(version_to_look_for))
        CloudFoundry.started_apps = started_apps

        commons.print_msg(CloudFoundry.clazz, method, "found {} started apps".format(len(started_apps)))

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _determine_manifests(self):
        method = '_determine_manifests'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        if os.path.isfile("{}.manifest.yml".format(self.config.build_env)):
            manifest = self.config.build_env + '.manifest.yml'
        elif os.path.isfile("{dir}/{env}.manifest.yml".format(dir=self.config.push_location,
                                                              env=self.config.build_env)):
            manifest = "{dir}/{env}.manifest.yml".format(dir=self.config.push_location,
                                                         env=self.config.build_env)
        else:
            commons.print_msg(CloudFoundry.clazz, method, "Failed to find manifest file {}.manifest.yml".format(
                self.config.build_env), 'ERROR')
            exit(1)

        # noinspection PyUnboundLocalVariable
        commons.print_msg(CloudFoundry.clazz, method, "Using manifest {}".format(manifest))

        commons.print_msg(CloudFoundry.clazz, method, 'end')

        return manifest

    def _cf_push(self, manifest, blue_green=None):
        method = '_cf_push'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        commons.print_msg(CloudFoundry.clazz, method, "Using manifest {}".format(manifest))

        if self.config.artifact_extension is None or self.config.artifact_extension in ('zip', 'tar', 'tar.gz'):
            # deployed from github directly or it's a zip, tar, tar.gz file
            file_to_push = self.config.push_location
        else:
            file_to_push = "{dir}/{file}".format(dir=self.config.push_location, file=self.find_deployable(
                self.config.artifact_extension, self.config.push_location))

        buildpack = "-b {}".format(os.getenv('CF_BUILDPACK')) if os.getenv('CF_BUILDPACK') else ""

        nostart = "--no-start" if blue_green else ""

        cmd = CloudFoundry.path_to_cf + "cf push {project_name}-{version} -p {pushlocation} -f {manifest} {buildpack} {nostart}".format(project_name=self.config.project_name,
                                            version=self.config.version_number,
                                            pushlocation=file_to_push,
                                            manifest=manifest,
                                            buildpack=buildpack,
                                            nostart=nostart)

        commons.print_msg(CloudFoundry.clazz, method, cmd.split())
        cf_push = subprocess.Popen(cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        push_failed = False

        while cf_push.poll() is None:
            line = cf_push.stdout.readline().decode('utf-8').strip(' \r\n')
            if(len(line) > 0):
                commons.print_msg(CloudFoundry.clazz, method, line)

        try:
            cf_push.communicate(timeout=300)

            if cf_push.returncode != 0:
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}.  Return code of {rtn}."
                                  .format(command=cmd,
                                         rtn=cf_push.returncode),
                                  'ERROR')
                push_failed = True

        except TimeoutExpired:
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd), 'ERROR')
            push_failed = True

        if push_failed:
            os.system('stty sane')
            self._cf_logout()
            exit(1)

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    # noinspection PyUnboundLocalVariable
    def _stop_old_app_servers(self):
        method = '_stop_old_app_servers'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        stop_old_apps_failed = False

        version_to_look_for = "{name}-{version}".format(name=self.config.project_name.lower(),
                                                        version=self.config.version_number)

        for line in CloudFoundry.started_apps:
            if line.name.lower() != version_to_look_for:
                commons.print_msg(CloudFoundry.clazz, method, "Scaling down {}".format(line.name))

                cmd = "{path}cf scale {app} -i 1".format(path=CloudFoundry.path_to_cf,
                                                         app=line.name)

                commons.print_msg(CloudFoundry.clazz, method, cmd)
                cf_scale = subprocess.Popen(cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

                try:
                    cf_scale_output, errs = cf_scale.communicate(timeout=120)

                    for scale_line in cf_scale_output.splitlines():
                        commons.print_msg(CloudFoundry.clazz, method, scale_line.decode('utf-8'))

                    if cf_scale.returncode != 0:
                        commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}"
                                                                     "".format(command=cmd, rtn=cf_scale.returncode),
                                         'WARN')
                        stop_old_apps_failed = True

                except TimeoutExpired:
                    commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd), 'WARN')
                    stop_old_apps_failed = True

                stop_cmd = "{path}cf stop {project}".format(path=CloudFoundry.path_to_cf,
                                                            project=line.name)

                commons.print_msg(CloudFoundry.clazz, method, stop_cmd)
                cf_stop = subprocess.Popen(stop_cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

                try:
                    cf_stop_output, errs = cf_stop.communicate(timeout=120)

                    for stop_line in cf_stop_output.splitlines():
                        commons.print_msg(CloudFoundry.clazz, method, stop_line.decode("utf-8"))

                    if cf_scale.returncode != 0:
                        commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}"
                                                                     "".format(command=cmd, rtn=cf_stop.returncode),
                                         'WARN')
                        stop_old_apps_failed = True

                except TimeoutExpired:
                    commons.print_msg(CloudFoundry.clazz, method, "Timed out calling".format(cmd), 'WARN')
                    stop_old_apps_failed = True
            else:
                commons.print_msg(CloudFoundry.clazz, method, "Skipping scale down for {}".format(line.name))

        # if stop_old_apps_failed:
        #     cf_stop.kill()
        #     # cf_stop.communicate()
        #     os.system('stty sane')
        #     self._cf_logout()

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _unmap_delete_previous_versions(self):
        method = '_unmap_delete_previous_versions'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        unmap_delete_previous_versions_failed = False

        for line in CloudFoundry.stopped_apps:
            if "{proj}-{ver}".format(proj=self.config.project_name,
                                     ver=self.config.version_number).lower() == line.name.lower():
                commons.print_msg(CloudFoundry.clazz, method, "{} exists. Not removing routes for it.".format(
                    line.name.lower()))
            else:
                bearer_token = "bearer {access_token}".format(access_token=self.api_token)

                pcf_route_headers = {'Authorization': bearer_token}

                apps_url = "https://{api}/v2/apps/{guid}/routes".format(api=CloudFoundry.cf_api_endpoint, guid=line.guid)
                try:
                    resp = requests.get(apps_url, headers=pcf_route_headers, verify=False)
                except requests.ConnectionError:
                    commons.print_msg(CloudFoundry.clazz, method, 'Request to Cloud Foundry timed out.', 'ERROR')
                    exit(1)
                except:
                    commons.print_msg(CloudFoundry.clazz, method,
                                      "The cloud foundry api routes call failed to {} has failed".
                                      format(apps_url), 'ERROR')
                    exit(1)

                json_data = json.loads(resp.text)

                if CloudFoundry.cf_domain is not None:
                    try:
                        for i, route in enumerate(json_data['resources']):
                            commons.print_msg(CloudFoundry.clazz, method, "Removing route {route} from {line}".format(
                                route=route['entity']['host'], line=line.name))

                            cmd = "{path}cf unmap-route {old_app} {cf_domain} -n {route_line}".format(
                                path=CloudFoundry.path_to_cf,
                                old_app=line.name,
                                cf_domain=CloudFoundry.cf_domain,
                                route_line=route['entity']['host'])

                            commons.print_msg(CloudFoundry.clazz, method, cmd)

                            unmap_route = subprocess.Popen(cmd.split(), shell=False, stdout=subprocess.PIPE,
                                                           stderr=subprocess.STDOUT)

                            try:
                                unmap_route_output, errs = unmap_route.communicate(timeout=120)

                                for unmapped_route in unmap_route_output.splitlines():
                                    commons.print_msg(CloudFoundry.clazz, method, unmapped_route.decode("utf-8"))

                                if unmap_route.returncode != 0:
                                    unmap_delete_previous_versions_failed = True
                                    commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return "
                                                                                  "code of {rtn}".format(
                                        command=cmd,
                                        rtn=unmap_route.returncode),
                                                      'ERROR')

                            except TimeoutExpired:
                                unmap_delete_previous_versions_failed = True
                                commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd),
                                                  'ERROR')

                    except TimeoutExpired:
                        commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd), 'ERROR')
                        unmap_delete_previous_versions_failed = True

                if unmap_delete_previous_versions_failed is False:
                    delete_cmd = "{path}cf delete {project} -f".format(project=line.name,
                                                                       path=CloudFoundry.path_to_cf)

                    commons.print_msg(CloudFoundry.clazz, method, delete_cmd)

                    delete_app = subprocess.Popen(delete_cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

                    try:
                        delete_app_output, errs = delete_app.communicate(timeout=120)

                        for deleted_app in delete_app_output.splitlines():
                            commons.print_msg(CloudFoundry.clazz, method, deleted_app.decode("utf-8"))

                        if delete_app.returncode != 0:
                            commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}"
                                              .format(command=cmd,
                                                     rtn=delete_app.returncode),
                                             'ERROR')

                    except TimeoutExpired:
                        commons.print_msg(CloudFoundry.clazz, method, "Timed out calling".format(delete_cmd), 'ERROR')
                        delete_app.kill()
                        delete_app.communicate()
                        os.system('stty sane')

                if unmap_delete_previous_versions_failed:
                    os.system('stty sane')
                    self._cf_logout()
                    exit(1)

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _cf_logout(self):
        method = '_cf_logout'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        cmd = "{}cf logout".format(CloudFoundry.path_to_cf)

        cf_logout = subprocess.Popen(cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        logout_failed = False

        try:
            cf_logout_output, errs = cf_logout.communicate(timeout=120)

            for line in cf_logout_output.splitlines():
                commons.print_msg(CloudFoundry.clazz, method, line.decode('utf-8'))

            if cf_logout.returncode != 0:
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}"
                                  .format(command=cmd,
                                         rtn=cf_logout.returncode),
                                 'ERROR')
                logout_failed = True

        except TimeoutExpired:
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd), 'ERROR')
            logout_failed = True

        if logout_failed:
            cf_logout.kill()
            os.system('stty sane')
            exit(1)

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _cf_login(self):
        method = 'cf_login'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        cmd = "{path}cf login -a {cf_api_endpoint} -u {cf_user} -p {cf_pwd} -o \"{cf_org}\" -s \"{cf_space}\" --skip-ssl-validation".format(
            path=CloudFoundry.path_to_cf,
            cf_api_endpoint=CloudFoundry.cf_api_endpoint,
            cf_user=CloudFoundry.cf_user,
            cf_pwd=CloudFoundry.cf_pwd,
            cf_org=CloudFoundry.cf_org,
            cf_space=CloudFoundry.cf_space
        )

        cmd_array = "{path}cf login -a {cf_api_endpoint} -u {cf_user} -p {cf_pwd} -o".format(
            path=CloudFoundry.path_to_cf,
            cf_api_endpoint=CloudFoundry.cf_api_endpoint,
            cf_user=CloudFoundry.cf_user,
            cf_pwd=CloudFoundry.cf_pwd
        ).split()
        cmd_array.append(CloudFoundry.cf_org)
        cmd_array.append("-s")
        cmd_array.append(CloudFoundry.cf_space)
        cmd_array.append("--skip-ssl-validation")

        cf_login = subprocess.Popen(cmd_array, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        login_failed = False

        while cf_login.poll() is None:
            line = cf_login.stdout.readline().decode('utf-8').strip(' \r\n')
            if(len(line) > 0):
                commons.print_msg(CloudFoundry.clazz, method, line)

            if 'credentials were rejected' in line.lower():
                commons.print_msg(CloudFoundry.clazz, method, "Make sure that your credentials are correct for {}"
                                  .format(CloudFoundry.cf_user), 'ERROR')
                login_failed = True

        try:
            cf_login_output, errs = cf_login.communicate(timeout=120)

            for line in cf_login_output.splitlines():
                commons.print_msg(CloudFoundry.clazz, method, line.decode('utf-8'))

            if cf_login.returncode != 0:
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling cf login. Return code of {rtn}. Make "
                                                             "sure the user {usr} has proper permission to deploy.",
                                 'ERROR')
                login_failed = True

        except TimeoutExpired:
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling CF LOGIN.  Make sure that your "
                                                         "credentials are correct for {}".format(CloudFoundry.cf_user),
                             'ERROR')
            login_failed = True

        if login_failed:
            cf_login.kill()
            os.system('stty sane')
            exit(1)

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _cf_login_check(self):
        method = 'cf_login_check'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        cmd_api = "{path}cf api {api} --skip-ssl-validation".format(path=CloudFoundry.path_to_cf,
                                          api=CloudFoundry.cf_api_endpoint)
        
        commons.print_msg(CloudFoundry.clazz, method, cmd_api)

        cf_api = subprocess.Popen(cmd_api.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        try:
            cf_api_output, cf_api_err = cf_api.communicate(timeout=120)

            for api_line in cf_api_output.splitlines():
                commons.print_msg(CloudFoundry.clazz, method, api_line.decode('utf-8'))

            if cf_api.returncode != 0:
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}".format(
                                 command=cmd_api, rtn=cf_api.returncode), 'ERROR')
                exit(1)

        except TimeoutExpired:
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd_api), 'ERROR')

        # Test user/pwd login
        cmd_auth = "{path}cf auth {cf_user} {cf_pwd}".format(path=CloudFoundry.path_to_cf,
                                                         cf_user=CloudFoundry.cf_user,
                                                         cf_pwd=CloudFoundry.cf_pwd)

        cf_login = subprocess.Popen(cmd_auth.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        
        try:
            cf_login_output, cf_login_err = cf_login.communicate(timeout=120)

            for cf_login_line in cf_login_output.splitlines():
                commons.print_msg(CloudFoundry.clazz, method, cf_login_line.decode('utf-8'))

            if cf_login.returncode != 0:
                commons.print_msg(CloudFoundry.clazz, method, "Make sure that your credentials are correct for {usr}. "
                                                             "\r\n Return Code: {rtn}".format(usr=CloudFoundry.cf_user,
                                                                                              rtn=cf_login.returncode),
                                 'ERROR')
                exit(1)

        except TimeoutExpired:
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling login for {}".format(
                CloudFoundry.cf_user), 'ERROR')

        cmd_target_array = '{path}cf target -o'.format(path=CloudFoundry.path_to_cf).split()
        cmd_target_array.append(CloudFoundry.cf_org)
        cmd_target_array.append("-s")
        cmd_target_array.append(CloudFoundry.cf_space)
        
        cf_target = subprocess.Popen(cmd_target_array, shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        try:
            cf_target_output, cf_target_err = cf_target.communicate(timeout=120)

            for cf_target_line in cf_target_output.splitlines():
                commons.print_msg(CloudFoundry.clazz, method, cf_target_line.decode('utf-8'))

            if cf_target.returncode != 0:
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}".format(
                                 command=cmd_target_array, rtn=cf_target.returncode), 'ERROR')
                exit(1)

        except TimeoutExpired:
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd_target_array), 'ERROR')
            exit(1)

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _change_route_to_cold_route(self):
        method = '_change_route_to_cold_route'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')
        #
        # # cmd = "{path}cf routes | grep {app} | awk '{{print $1}}'".format(path=CloudFoundry.path_to_cf,
        # #                                                                  app=self.config.project_name + '-' + self.config.version_number)
        #
        #
        # cmd = "{path}cf app {app} | grep routes: | cut -d" " -f2-".format( path=CloudFoundry.path_to_cf,
        #                                                                   app=self.config.project_name + '-' + self.config.version_number)
        #
        # routes_to_make_cold = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)  # nosec
        #
        # make_cold_routes_failed = False
        #
        # try:
        #     routes_to_make_cold_output, errs = routes_to_make_cold.communicate(timeout=30)
        #
        #     for line in routes_to_make_cold_output.splitlines():
        #         commons.print_msg(CloudFoundry.clazz, method, line.decode('utf-8'))
        #
        #         if '-cold' not in line.decode('utf-8'):
        #
        #     if cf_logout.returncode != 0:
        #         commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}"
        #                           .format(command=cmd,
        #                                   rtn=cf_logout.returncode),
        #                           'ERROR')
        #         logout_failed = True
        #
        #
        #     CloudFoundry.stopped_apps, errs = stopped_apps.communicate(timeout=60)
        #
        #     delete_app = subprocess.Popen(delete_cmd.split(), shell=False, stdout=subprocess.PIPE,
        #                                   stderr=subprocess.STDOUT)
        #
        #     try:
        #         delete_app_output, errs = delete_app.communicate(timeout=120)
        #     if stopped_apps.returncode != 0:
        #         commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}".format(
        #             command=cmd, rtn=stopped_apps.returncode), 'ERROR')
        #         get_stopped_apps_failed = True
        # # get routes for application
        #
        # # loop through routes
        #
        #     # add new routes but with -cold
        #
        # # get routes for application
        #
        #     # unmap non-cold routes

    def _map_route(self, app, domain, host=None, route_path=None):
        method = '_map_route'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        cmd = "{path}cf map-route {app} {cf_domain} {host} {route_path}".format(
            path=CloudFoundry.path_to_cf,
            app=app,
            cf_domain=domain,
            host="--hostname {}".format(host) if host is not None else "",
            route_path="--path {}".format(route_path) if route_path is not None else "")

        commons.print_msg(CloudFoundry.clazz, method, cmd)

        map_route = subprocess.Popen(cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        map_route_failed = False

        try:
            map_route_output, errs = map_route.communicate(timeout=120)

            for mapped_route in map_route_output.splitlines():
                commons.print_msg(CloudFoundry.clazz, method, mapped_route.decode("utf-8"))

            if map_route.returncode != 0:
                map_route_failed = True
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return "
                                                              "code of {rtn}".format(command=cmd,
                                                                                     rtn=map_route.returncode),
                                  'ERROR')

        except TimeoutExpired:
            map_route_failed = True
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd), 'ERROR')

        if map_route_failed:
            os.system('stty sane')
            self._cf_logout()
            exit(1)

    def _unmap_route(self, app, domain, host=None, route_path=None):
        method = '_unmap_route'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        cmd = "{path}cf unmap-route {app} {cf_domain} {host} {route_path}".format(
            path=CloudFoundry.path_to_cf,
            app=app,
            cf_domain=domain,
            host="--hostname {}".format(host) if host is not None else "",
            route_path = "--path {}".format(route_path) if route_path is not None else "")

        commons.print_msg(CloudFoundry.clazz, method, cmd)

        unmap_route = subprocess.Popen(cmd.split(), shell=False, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)

        unmap_delete_previous_versions_failed = False

        try:
            unmap_route_output, errs = unmap_route.communicate(timeout=120)

            for unmapped_route in unmap_route_output.splitlines():
                commons.print_msg(CloudFoundry.clazz, method, unmapped_route.decode("utf-8"))

            if unmap_route.returncode != 0:
                unmap_delete_previous_versions_failed = True
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return "
                                                              "code of {rtn}".format( command=cmd,
                                                                                      rtn=unmap_route.returncode),
                                  'ERROR')

        except TimeoutExpired:
            unmap_delete_previous_versions_failed = True
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd), 'ERROR')

        if unmap_delete_previous_versions_failed:
            os.system('stty sane')
            self._cf_logout()
            exit(1)

    def _get_routes(self, app_name=None, app_version=None, cold_routes=False):
        method = '_get_routes'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        all_routes_cmd = "{path}cf routes".format(path=CloudFoundry.path_to_cf)
        all_routes = subprocess.Popen(all_routes_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        existing_routes_output, err = all_routes.communicate(timeout=120)
        route_header = existing_routes_output.splitlines()[2].decode("utf-8")

        space_pos = route_header.index('space')
        host_pos = route_header.index('host')
        domain_pos = route_header.index('domain')
        port_pos = route_header.index('port')
        path_pos = route_header.index('path')
        type_pos = route_header.index('type')
        apps_pos = route_header.index('apps')
        service_pos = route_header.index('service')

        all_routes_cmd = "{path}cf routes".format(path=CloudFoundry.path_to_cf)

        app_search_string = "{app}{version}".format(app="{}-".format(app_name) if app_name is not None else "",
                                                    version=app_version if app_version is not None else "")
        filtered_application_cmd = "grep {}".format(app_search_string)
        all_routes = subprocess.Popen(all_routes_cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        filtered_applications = subprocess.Popen(filtered_application_cmd.split(), stdin=all_routes.stdout,
                                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if cold_routes:
            filter_cold_routes_cmd = "grep \\cold"
            filtered_applications_cold = subprocess.Popen(filter_cold_routes_cmd.split(), stdin=filtered_applications.stdout, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            existing_routes_output, err = filtered_applications_cold.communicate(timeout=120)
        else:
            existing_routes_output, err = filtered_applications.communicate(timeout=120)
        
        routes = []

        for route_line in existing_routes_output.splitlines():
            route = commons.Object()
            route.apps = route_line.decode("utf-8")[apps_pos:(service_pos - 1)].rstrip().split(',')
            host = route_line.decode("utf-8")[host_pos:(domain_pos - 1)].rstrip()
            route.domain = route_line.decode("utf-8")[domain_pos:(port_pos - 1)].rstrip()
            path = route_line.decode("utf-8")[path_pos:(type_pos - 1)].rstrip()
            if not path:
                route.path = None
            else: 
                route.path = path
            if not host:
                route.host = None
            else:
                route.host = host
            routes.append(route)

        for route in routes:
            commons.print_msg(CloudFoundry.clazz, method, "{host}.{domain}/{path}".format(host=route.host,
                                                                                          domain=route.domain,
                                                                                          path=route.path))

        return routes

    def cutover(self):
        method = 'cutover'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        self._verify_required_attributes()

        self.download_cf_cli()

        self._cf_login_check()

        self._cf_login()

        self._check_cf_version()

        self._get_stopped_apps()

        self._get_started_apps(True)

        self._stop_old_app_servers()

        self._unmap_delete_previous_versions()

    def promote(self):
        method = 'promote'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        self._verify_required_attributes()

        self.download_cf_cli()

        self._cf_login_check()

        self._cf_login()

        self._check_cf_version()
        
        cold_routes=self._get_routes(app_name=self.config.project_name, cold_routes=True)

        for route in cold_routes:
            for app in route.apps:
                path_without_cold = route.path.replace('/cold','')
                self._map_route(app=app,domain=route.domain, host=route.host, route_path=path_without_cold if path_without_cold else None) 
                self._unmap_route(app=app,domain=route.domain,host=route.host,route_path=route.path)
        
                self._restart_app(app)
        
    def deploy(self, force_deploy=False, manifest=None, blue_green=False):
        method = 'deploy'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        self.api_login()

        self._get_space_guid()

        self._verify_required_attributes()

        self.download_cf_cli()

        self._cf_login_check()

        self._cf_login()

        self._check_cf_version()

        self._get_stopped_apps()

        self._get_started_apps(force_deploy)

        if manifest is None:
            manifest = self._determine_manifests()

        # if blue/green, unmap any cold routes that exist
        if blue_green:
            cold_routes=self._get_routes(app_name=self.config.project_name, cold_routes=True)

            for route in cold_routes:
                # _self.unmap_route()
                for app in route.apps:
                    self._unmap_route(app=app,domain=route.domain,host=route.host,route_path=route.path)
        
        self._cf_push(manifest, blue_green)

        # if blue/green, map cold routes, unmap hot routes and start new app
        if blue_green:
            hot_routes = self._get_routes(app_name=self.config.project_name, app_version=self.config.version_number)

            for route in hot_routes:
                self._map_route(app="{app}-{version}".format(app=self.config.project_name, version=self.config.version_number),domain=route.domain, host=route.host, route_path="{}/cold".format(route.path if route.path is not None else ""))
                self._unmap_route(app="{app}-{version}".format(app=self.config.project_name, version=self.config.version_number),domain=route.domain, host=route.host, route_path=route.path) 

            self._start_app("{app}-{version}".format(app=self.config.project_name, version=self.config.version_number))

        if not blue_green and not os.getenv("AUTO_STOP"):
            self._stop_old_app_servers()

        if not blue_green and not force_deploy:
            # don't delete if force bc we want to ensure that there is always 1 non-started instance
            # for backup and force_deploy is used when you need to redeploy/replace an instance
            # that is currently running
            self._unmap_delete_previous_versions()

        commons.print_msg(CloudFoundry.clazz, method, 'DEPLOYMENT SUCCESSFUL')

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _start_app(self, app):
        method = '_start_app'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        cmd = "{path}cf start {app_name}".format(path=CloudFoundry.path_to_cf, app_name=app)
        cf_start = subprocess.Popen(cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        try:
            cf_start_output, errs = cf_start.communicate(timeout=120)

            if cf_start.returncode != 0:
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}".format(
                    command=cmd, rtn=cf_start.returncode), 'ERROR')

                os.system('stty sane')
                self._cf_logout()
                exit(1)

        except TimeoutExpired:
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd), 'ERROR')
            cf_start.kill()
            os.system('stty sane')
            self._cf_logout()
            exit(1)

        commons.print_msg(CloudFoundry.clazz, method, 'end')

    def _restart_app(self, app):
        method = '_restart_app'
        commons.print_msg(CloudFoundry.clazz, method, 'begin')

        cmd = "{path}cf restart {app_name}".format(path=CloudFoundry.path_to_cf, app_name=app)
        cf_start = subprocess.Popen(cmd.split(), shell=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        try:
            cf_start_output, errs = cf_start.communicate(timeout=120)

            if cf_start.returncode != 0:
                commons.print_msg(CloudFoundry.clazz, method, "Failed calling {command}. Return code of {rtn}".format(
                    command=cmd, rtn=cf_start.returncode), 'ERROR')

                os.system('stty sane')
                self._cf_logout()
                exit(1)

        except TimeoutExpired:
            commons.print_msg(CloudFoundry.clazz, method, "Timed out calling {}".format(cmd), 'ERROR')
            cf_start.kill()
            os.system('stty sane')
            self._cf_logout()
            exit(1)

        commons.print_msg(CloudFoundry.clazz, method, 'end')
