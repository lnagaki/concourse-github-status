import time
import os
import re
import sys
import json
import requests
import subprocess
import uuid
import functools as fn
import logging
from pprint import pformat
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import (
    Optional,
)
import http.client


logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
logger = logging.getLogger(__name__)
run = fn.partial(subprocess.run, check=True, capture_output=True, encoding='utf-8')

# https://stackoverflow.com/questions/16337511/log-all-requests-from-the-python-requests-module
httpclient_logger = logging.getLogger("http.client")
def httpclient_logging_patch(level=logging.DEBUG):
    """Enable HTTPConnection debug logging to the logging framework"""

    def httpclient_log(*args):
        httpclient_logger.log(level, " ".join(args))

    # mask the print() built-in in the http.client module to use
    # logging instead
    http.client.print = httpclient_log
    # enable debugging
    http.client.HTTPConnection.debuglevel = 1
httpclient_logging_patch()


@fn.lru_cache
def stdin():
    return sys.stdin.read()


class BuildEnvironment:
    """Get details about the concourse build environment"""
    ENV_VARS = (
        'BUILD_ID',
        'BUILD_NAME',
        'BUILD_JOB_NAME',
        'BUILD_PIPELINE_NAME',
        'BUILD_TEAM_NAME',
        'ATC_EXTERNAL_URL',
    )

    @property
    def build_dir(self):
        return sys.argv[1]

    @property
    @fn.lru_cache
    def input_data(self):
        d = json.loads(stdin())
        logger.debug('input data: %s', d)
        return d

    @property
    def params(self):
        return self.input_data.get('params', {})

    @property
    def source(self):
        return Source.from_dict(self.input_data['source'])

    def __getattr__(self, attr):
        if attr.upper() in self.ENV_VARS:
            return os.environ.get(attr.upper(), '')
        raise AttributeError(f'No such attribute: {attr}')


@dataclass
class Source:
    owner: str
    repository: str
    branch: str
    context: str
    endpoint: str
    access_token: str

    @classmethod
    def from_dict(cls, d):
        return cls(
            owner=d['owner'],
            repository=d['repository'],
            access_token=d['access_token'],
            branch=d.get('branch', 'master'),
            context=d.get('context', 'default'),
            endpoint=d.get('endpoint', GithubAPI.DEFAULT_ENDPOINT),
        )



@dataclass
class OutParams:
    """Parsed parameters for the `out` operation"""
    commit: str
    state: str
    description: str
    target_url: str

    @classmethod
    def from_build(cls, env: BuildEnvironment):
        is_pipeline_build = env.build_pipeline_name and env.build_job_name

        if is_pipeline_build:
            default_description = f'Concourse build for {env.build_pipeline_name}/{env.build_job_name}'
        else:
            default_description = f'ad hoc Concourse build #{env.build_id}'

        if description_path := env.params.get('description_path'):
            description = Path(description_path).read_text()
        else:
            description = env.params.get('descripion', default_description)

        default_target_url = f'{env.atc_external_url}'
        if is_pipeline_build:
            default_target_url += (f'/teams/{env.build_team_name}'
                                   f'/pipelines/{env.build_pipeline_name}'
                                   f'/jobs/{env.build_job_name}')
        default_target_url += f'/builds/{env.build_id}'

        return cls(
            commit=get_commit_sha(env.build_dir, env.params['commit']),
            state=env.params['state'],
            description=description,
            target_url=env.params.get('target_url', default_target_url),
        )


@dataclass
class InParams:
    """Parsed parameters for the `in` operation"""
    commit_ref: str = 'master'
    output_path: str = 'github-build-status.json'

    @classmethod
    def from_build(cls, env: BuildEnvironment):
        return cls(**env.params)


class GithubAPI(requests.Session):
    DEFAULT_ENDPOINT = 'https://api.github.com'

    def __init__(self, token, endpoint=DEFAULT_ENDPOINT, **kwargs):
        super().__init__(**kwargs)
        self.endpoint = endpoint
        self.token = token
        self.headers['Authorization'] = f'token {token}'

    def get_status(self, owner, repo, commit_ref):
        url = (f'{self.endpoint}/repos/{owner}/{repo}'
               f'/commits/{commit_ref}/status')
        resp = self.get(url)
        resp.raise_for_status()
        return resp

    def set_status(self, *, owner, repo, commit_sha, state, description, target_url, context='default'):
        url = (f'{self.endpoint}/repos/{owner}/{repo}'
               f'/statuses/{commit_sha}')

        json_data = {
            'state': state,
            'target_url': target_url,
            'context': context,
        }
        if description:
            json_data['description'] = description
        resp = self.post(url, json=json_data)
        resp.raise_for_status()
        return resp


def status_context(env: BuildEnvironment):
    is_pipeline_build = env.build_pipeline_name and env.build_job_name
    if is_pipeline_build:
        return f'{env.build_pipeline_name}/{env.build_job_name}'
    else:
        return f'adhoc/{env.build_id}'


def get_commit_sha(base_dir, sha_or_repo):
    path = Path(base_dir) / sha_or_repo
    if path.is_dir():
        return path.joinpath('.git', 'HEAD').read_text().strip()
    elif path.is_file():
        return path.read_text().strip()
    else:
        return sha_or_repo


def main_in():
    build_env = BuildEnvironment()
    params = InParams.from_build(build_env)

    api = GithubAPI(build_env.source.access_token, build_env.source.endpoint)
    resp = api.get_status(
        owner=build_env.source.owner,
        repo=build_env.source.repository,
        commit_ref=params.commit_ref,
    )

    with open(params.output_path, 'w') as f:
        f.write(resp.text)

    # The outputed version cannot be the actual build status id because
    # concourse expects the `in` version to equal the `check` version.
    # We have no way of knowing the desired commit ref during the `check` phase
    # so we just echo back the random id generated in the check step.
    output = {'version': build_env.input_data['version'], 'metadata': [
        {'name': 'state', 'value': resp.json()['state']},
        {'name': 'sha', 'value': resp.json()['sha']},
        {'name': 'commit_url', 'value': resp.json()['commit_url']},
        {'name': 'total_count', 'value': str(resp.json()['total_count'])},
    ]}
    json.dump(output, sys.stdout)


def main_out():
    build_env = BuildEnvironment()
    params = OutParams.from_build(build_env)

    api = GithubAPI(build_env.source.access_token, build_env.source.endpoint)
    resp = api.set_status(
        owner=build_env.source.owner,
        repo=build_env.source.repository,
        commit_sha=params.commit,
        state=params.state,
        description=params.description,
        target_url=params.target_url,
    )

    output = {
        'version': {'ref': str(resp.json()['id'])},
        'metadata': [
            {'name': 'sha', 'value': params.commit},
            {'name': 'state', 'value': params.state},
            {'name': 'url', 'value': resp.json()['url']}
        ]
    }
    json.dump(output, sys.stdout)


def main_check():
    json.dump([{'ref': str(uuid.uuid4())}], sys.stdout)
