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
    ENV_VARS = (
        'build_id',
        'build_name',
        'build_job_name',
        'build_pipeline_name',
        'build_team_name',
        'atc_external_url',
    )

    @property
    def build_dir(self):
        return sys.argv[1]

    @property
    @fn.lru_cache
    def input_data(self):
        return json.loads(stdin())

    def __getattr__(self, attr):
        if attr in self.ENV_VARS:
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
    commit: str
    state: str
    description: str
    target_url: str

    @classmethod
    def from_build(cls, env: BuildEnvironment):
        params = env.input_data['params']
        is_pipeline_build = env.build_pipeline_name and env.build_job_name

        if is_pipeline_build:
            default_description = f'{env.build_pipeline_name}/{env.build_job_name}'
        else:
            default_description = f'ad hoc build #{env.build_id}'

        if description_path := params.get('description_path'):
            description = Path(description_path).read_text()
        else:
            description = params.get('descripion', default_description)

        default_target_url = f'{env.atc_external_url}'
        if is_pipeline_build:
            default_target_url += (f'/teams/{env.build_team_name}'
                                   f'/pipelines/{env.build_pipeline_name}'
                                   f'/jobs/{env.build_job_name}')
        default_target_url += f'/builds/{env.build_id}'

        return cls(
            commit=get_commit_sha(env.build_dir, params['commit']),
            state=params['state'],
            description=description,
            target_url=params.get('target_url', default_target_url),
        )


class GithubAPI(requests.Session):
    DEFAULT_ENDPOINT = 'https://api.github.com'

    def __init__(self, owner, repository, token, endpoint=DEFAULT_ENDPOINT, **kwargs):
        super().__init__(**kwargs)
        self.owner = owner
        self.repository = repository
        self.endpoint = endpoint
        self.token = token
        self.headers['Authorization'] = f'token {token}'

    def status_url(self, commit_ref=None):
        url = (f'{self.endpoint}/repos'
               f'/{self.owner}/{self.repository}/statuses')
        if commit_ref is not None:
            url += f'/{commit_ref}'
        return url

    def get_status(self, commit_sha, context=None):
        pass

    def set_status(self, commit_sha, state, description, target_url, context='default'):
        json_data = {
            'state': state,
            'target_url': target_url,
            'context': context,
        }
        if description:
            json_data['description'] = description
        resp = self.post(self.status_url(commit_sha), json=json_data)
        resp.raise_for_status()
        return resp


def get_commit_sha(base_dir, sha_or_repo):
    path = Path(base_dir) / sha_or_repo
    if path.is_dir():
        return path.joinpath('.git', 'HEAD').read_text().strip()
    elif path.is_file():
        return path.read_text().strip()
    else:
        return sha_or_repo


def ref():
    return int(time.time() // 120)


def show_env():
    if sys.stdin.isatty():
        logger.info('stdin is a tty')
    else:
        logger.info(f'stdin: {stdin()}')
    logger.info(f'\ncwd: {os.getcwd()}')
    logger.info(f'\nargv: {sys.argv}')
    logger.info(f'\nenv: {pformat(dict(os.environ))}')
    try:
        mount_proc = run(['mount'])
    except Exception:
        logger.info('count not run mount')
    else:
        logger.info(f'\nmounts:\n{mount_proc.stdout}')
    # build_paths = list(Path(BUILD_DIR).iterdir())
    # logger.info('\nbuild paths:', pformat(build_paths))
    find = run(['find', '/', '-name', 'repository'], check=False)
    logger.info(f'\nfind repository status {find.returncode}:\n{find.stdout}{find.stderr}')


def main_in():
    show_env()
    input_data = json.loads(stdin())
    output = {'version': input_data['version'], 'metadata': []}
    json.dump(output, sys.stdout)


def main_out():
    show_env()
    build_env = BuildEnvironment()

    source = Source.from_dict(build_env.input_data['source'])
    params = OutParams.from_build(build_env)

    api = GithubAPI(source.owner, source.repository, source.access_token, source.endpoint)
    resp = api.set_status(params.commit, params.state, params.description,
                          params.target_url)

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
