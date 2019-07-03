import os
import subprocess
from unittest.mock import MagicMock
from unittest.mock import patch
import json
import pytest
from flow.cloud.cloudfoundry.cloudfoundry import CloudFoundry

from flow.buildconfig import BuildConfig

mock_build_config_dict = {
    "projectInfo": {
        "name": "testproject"
    },
    "environments": {
        "unittest": {
            "cf": {
                "apiEndpoint": "api.run-np.fake.com",
                "domain": "apps-np.fake.com",
                "space": "development",
                "org": "ci"
            },
            "artifactCategory": "snapshot",
            "associatedBranchName": "develop"
        }
    }
}

mock_build_config_dict_missing_project_name = {
    "projectInfo": {
    },
    "environments": {
        "unittest": {
            "cf": {
                "apiEndpoint": "api.run-np.fake.com",
                "domain": "apps-np.fake.com",
                "space": "development",
                "org": "ci"
            },
            "artifactCategory": "snapshot",
            "associatedBranchName": "develop"
        }
    }
}

mock_build_config_missing_space_dict = {
    "projectInfo": {
        "name": "testproject"
    },
    "environments": {
        "unittest": {
            "cf": {
                "apiEndpoint": "api.run-np.fake.com",
                "domain": "apps-np.fake.com",
                "org": "ci"
            },
            "artifactCategory": "snapshot",
            "associatedBranchName": "develop"
        }
    }
}


mock_build_config_missing_apiEndpoint_dict = {
    "projectInfo": {
        "name": "testproject"
    },
    "environments": {
        "unittest": {
            "cf": {
                "domain": "apps-np.fake.com",
                "space": "development",
                "org": "ci"
            },
            "artifactCategory": "snapshot",
            "associatedBranchName": "develop"
        }
    }
}


mock_build_config_missing_org_dict = {
    "projectInfo": {
        "name": "testproject"
    },
    "environments": {
        "unittest": {
            "cf": {
                "apiEndpoint": "api.run-np.fake.com",
                "domain": "apps-np.fake.com",
                "space": "development"
            },
            "artifactCategory": "snapshot",
            "associatedBranchName": "develop"
        }
    }
}

mock_running_applications = {
    "total_results": 1,
    "total_pages": 1,
    "prev_url": "null",
    "next_url": "null",
    "resources": [
        {
            "metadata": {
                "guid": "abc1234-e751-432f-9cc5-f8b3ec2f80aa",
                "url": "/v2/apps/abc1234-e751-432f-9cc5-f8b3ec2f80aa",
                "created_at": "2018-09-17T19:30:47Z",
                "updated_at": "2019-06-12T12:17:30Z"
            },
            "entity": {
                "name": "CI-HelloWorld-v2.9.0+1",
                "production": "false",
                "space_guid": "abc4444-3202-429c-9223-62556b4385a8",
                "stack_guid": "zzzz-88dd-4734-a963-d692716760d1",
                "buildpack": "hwc_buildpack",
                "detected_buildpack": "hwc",
                "detected_buildpack_guid": "yyyy-dee3-4630-970b-144df8636a8e",
                "environment_json": {
                    "Redis:Channel": "configuration:Image.yml",
                    "VaultServiceBindingName": "vault",
                    "management:endpoints:path": "/abc1234/cloudfoundryapplication",
                    "spring:cloud:config:name": "Image",
                    "spring:cloud:config:timeout": "60000",
                    "spring:cloud:config:validate_certificates": "false"
                },
                "memory": 512,
                "instances": 1,
                "disk_quota": 512,
                "state": "STARTED",
                "version": "zzz-00ea-4876-87e4-7290249b446a",
                "command": "null",
                "console": "false",
                "debug": "null",
                "staging_task_id": "aaa-9060-44dd-946f-df765787bb25",
                "package_state": "STAGED",
                "health_check_type": "http",
                "health_check_timeout": "null",
                "health_check_http_endpoint": "/test/test.ashx?Action=healthcheck",
                "staging_failed_reason": "null",
                "staging_failed_description": "null",
                "diego": "true",
                "docker_image": "null",
                "docker_credentials": {
                    "username": "null",
                    "password": "null"
                },
                "package_updated_at": "2019-06-12T12:17:26Z",
                "detected_start_command": ".cloudfoundry\\hwc.exe",
                "enable_ssh": "true",
                "ports": [
                    "8080"
                ],
                "space_url": "/v2/spaces/abc-3202-429c-9223-62556b4385a8",
                "stack_url": "/v2/stacks/def-88dd-4734-a963-d692716760d1",
                "routes_url": "/v2/apps/ghi-e751-432f-9cc5-f8b3ec2f80aa/routes",
                "events_url": "/v2/apps/jkl-e751-432f-9cc5-f8b3ec2f80aa/events",
                "service_bindings_url": "/v2/apps/12345-e751-432f-9cc5-f8b3ec2f80aa/service_bindings",
                "route_mappings_url": "/v2/apps/55555-e751-432f-9cc5-f8b3ec2f80aa/route_mappings"
            }
        }
    ]
}



mock_started_apps_already_started = 'CI-HelloWorld-v2.9.0+1'

def test_verify_required_attributes_missing_user(monkeypatch):
    if os.getenv('DEPLOYMENT_USER'):
        monkeypatch.delenv('DEPLOYMENT_USER')

    with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
        with pytest.raises(SystemExit):
            _cf = CloudFoundry()
            _cf._verify_required_attributes()

    mock_printmsg_fn.assert_called_with('CloudFoundry', '_verify_required_attributes', "No User Id. Did you forget to define environment variable 'DEPLOYMENT_USER?", 'ERROR')


def test_verify_required_attributes_missing_pwd(monkeypatch):
    monkeypatch.setenv('DEPLOYMENT_USER', 'DUMMY')

    if os.getenv('DEPLOYMENT_PWD'):
        monkeypatch.delenv('DEPLOYMENT_PWD')

    with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
        with pytest.raises(SystemExit):
            _cf = CloudFoundry()
            _cf._verify_required_attributes()

    mock_printmsg_fn.assert_called_with('CloudFoundry', '_verify_required_attributes', "No User Password. Did you forget to define environment variable 'DEPLOYMENT_PWD'?", 'ERROR')


def test_verify_required_attributes_missing_project_name(monkeypatch):
    monkeypatch.setenv('DEPLOYMENT_USER', 'DUMMY')
    monkeypatch.setenv('DEPLOYMENT_PWD', 'DUMMY')

    with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
        with pytest.raises(SystemExit):
            _b = MagicMock(BuildConfig)
            _b.build_env_info = mock_build_config_dict_missing_project_name['environments']['unittest']
            _b.json_config = mock_build_config_dict_missing_project_name
            _b.version_number = None
            _b.project_name = None

            _cf = CloudFoundry(_b)
            _cf._verify_required_attributes()

    mock_printmsg_fn.assert_called_with('CloudFoundry', '_verify_required_attributes', "The build config associated with cloudfoundry is missing key 'name'", 'ERROR')


def test_verify_required_attributes_missing_endpoint(monkeypatch):
    monkeypatch.setenv('DEPLOYMENT_USER', 'DUMMY')
    monkeypatch.setenv('DEPLOYMENT_PWD', 'DUMMY')

    with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
        with pytest.raises(SystemExit):
            _b = MagicMock(BuildConfig)
            _b.build_env_info = mock_build_config_missing_apiEndpoint_dict['environments']['unittest']
            _b.json_config = mock_build_config_missing_apiEndpoint_dict
            _b.version_number = None

            _cf = CloudFoundry(_b)
            _cf._verify_required_attributes()

    mock_printmsg_fn.assert_called_with('CloudFoundry', '_verify_required_attributes', "The build config associated with cloudfoundry is missing key 'apiEndpoint'", 'ERROR')


def test_verify_required_attributes_missing_space(monkeypatch):
    monkeypatch.setenv('DEPLOYMENT_USER', 'DUMMY')
    monkeypatch.setenv('DEPLOYMENT_PWD', 'DUMMY')

    with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
        with pytest.raises(SystemExit):
            _b = MagicMock(BuildConfig)
            _b.build_env_info = mock_build_config_missing_space_dict['environments']['unittest']
            _b.json_config = mock_build_config_missing_space_dict
            _b.version_number = None

            _cf = CloudFoundry(_b)
            _cf._verify_required_attributes()

    mock_printmsg_fn.assert_called_with('CloudFoundry', '_verify_required_attributes', "The build config associated with cloudfoundry is missing key 'space'", 'ERROR')


def test_verify_required_attributes_missing_org(monkeypatch):
    monkeypatch.setenv('DEPLOYMENT_USER', 'DUMMY')
    monkeypatch.setenv('DEPLOYMENT_PWD', 'DUMMY')

    with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
        with pytest.raises(SystemExit):
            _b = MagicMock(BuildConfig)
            _b.build_env_info = mock_build_config_missing_org_dict['environments']['unittest']
            _b.json_config = mock_build_config_missing_org_dict
            _b.version_number = None

            _cf = CloudFoundry(_b)
            _cf._verify_required_attributes()

    mock_printmsg_fn.assert_called_with('CloudFoundry', '_verify_required_attributes', "The build config associated with cloudfoundry is missing key 'org'", 'ERROR')


def test_get_started_apps_already_started():
        with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
            with patch('requests.get', side_effect=mocked_requests_get):
                with pytest.raises(SystemExit):
                    _b = MagicMock(BuildConfig)
                    _b.project_name = 'CI-HelloWorld'
                    _b.version_number = 'v2.9.0+1'
                    _cf = CloudFoundry(_b)

                    with patch.object(_cf, '_cf_logout'):
                        _cf._get_started_apps()

        mock_printmsg_fn.assert_called_with('CloudFoundry', '_get_started_apps', "App version ci-helloworld-v2.9.0+1 already exists and is running. Cannot perform zero-downtime deployment.  To override, set force flag = 'true'", 'ERROR')



def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.text = json.dumps(json_data)
            self.status_code = status_code

        def json(self):
            return self.json_data

    return MockResponse(mock_running_applications, 200)


def test_get_started_apps_already_started_force_deploy():
        with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
            with patch('requests.get', side_effect=mocked_requests_get):
                _b = MagicMock(BuildConfig)
                _b.project_name = 'CI-HelloWorld'
                _b.version_number = 'v2.9.0+1'
                _cf = CloudFoundry(_b)

                with patch.object(_cf, '_cf_logout'):
                    _cf._get_started_apps(True)

        mock_printmsg_fn.assert_any_call('CloudFoundry', '_get_started_apps', "Already found ci-helloworld-v2.9.0+1 but force_deploy turned on. Continuing with deployment.  Downtime will occur during deployment.")


def test_find_deployable_multiple_files():
    with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
        with pytest.raises(SystemExit):
            with patch('os.listdir', return_value=['file1.txt', 'file2.txt', 'file3.txt']):
                with patch('os.path.isfile', return_value=True):
                    _b = MagicMock(BuildConfig)
                    _b.project_name = 'CI-HelloWorld'
                    _b.version_number = 'v2.9.0+1'
                    _b.push_location = 'fordeployment'
                    _cf = CloudFoundry(_b)

                    _cf.find_deployable('txt', 'fake_push_dir')

    mock_printmsg_fn.assert_called_with('Cloud', 'find_deployable', 'Found more than 1 artifact in fake_push_dir',
                                        'ERROR')

# def test_find_deployable_no_files_only_directories():
#     with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
#         with pytest.raises(SystemExit):
#             with patch('os.listdir', return_value=['file1.txt', 'file2.txt', 'file3.txt']):
#                 with patch('os.path.isfile', return_value=False):
#                     _b = MagicMock(BuildConfig)
#                     _b.project_name = 'CI-HelloWorld'
#                     _b.version_number = 'v2.9.0+1'
#                     _b.push_location = 'fordeployment'
#                     _cf = CloudFoundry(_b)
#                     _cf.find_deployable('txt', 'fake_push_dir')
#
#     mock_printmsg_fn.assert_called_with('Cloud', 'find_deployable', 'Could not find file of type txt in fake_push_dir',
#                                         'ERROR')


def test_find_deployable_no_files_only_directories():
    with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
        with pytest.raises(SystemExit):
            with patch('os.listdir', return_value=['file1.txt', 'file2.txt', 'file3.txt']):
                with patch('os.path.isfile', return_value=False):
                    _b = MagicMock(BuildConfig)
                    _b.project_name = 'CI-HelloWorld'
                    _b.version_number = 'v2.9.0+1'
                    _b.push_location = 'fordeployment'
                    _cf = CloudFoundry(_b)
                    _cf.find_deployable('txt', 'fake_push_dir')

    mock_printmsg_fn.assert_called_with('Cloud', 'find_deployable', 'Could not find file of type txt in fake_push_dir',
                                        'ERROR')

def test_find_deployable_one_file():
    with patch('flow.utils.commons.print_msg') as mock_printmsg_fn:
        with patch('zipfile.ZipFile') as mocked_ZipFile:
            mocked_ZipFile.return_value.returncode = 0
            with patch('os.listdir', return_value=['file1.jar', 'file2.abc', 'file3.abc']):
                with patch('os.path.isfile', return_value=True):
                    _b = MagicMock(BuildConfig)
                    _b.project_name = 'CI-HelloWorld'
                    _b.version_number = 'v2.9.0+1'
                    _b.push_location = 'fordeployment'
                    _cf = CloudFoundry(_b)

                    _cf.find_deployable('jar', 'fake_push_dir')

    mock_printmsg_fn.assert_any_call('Cloud', 'find_deployable', 'Looking for a jar in fake_push_dir')

