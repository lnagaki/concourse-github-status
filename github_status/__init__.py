import time
import os
import re
import sys
import json
import requests
import subprocess
import uuid
import functools as fn
from pprint import pformat
from dataclasses import dataclass, asdict
from pathlib import Path

# BUILD_ID = os.environ['BUILD_ID']
# DEFAULT_TARGET_URL = f'{os.environ["ATC_EXTERNAL_URL"]}/builds/{BUILD_ID}'


@fn.lru_cache
def stdin():
    return sys.stdin.read()


@dataclass
class Metadata:
    build_id: str
    build_name: str
    build_job_name: str
    build_pipeline_name: str
    build_team_name: str
    atc_external_url: str

    @classmethod
    def from_env(cls):
        return cls(**{
            name: os.environ.get(name.upper(), '')
            for name, field in cls.__dataclass_fields__.items()
        })


@dataclass
class Source:
    owner: str
    repository: str
    branch: str
    context: str
    endpoint: str

    @classmethod
    def from_dict(cls, d):
        return cls(
            owner=d['owner'],
            repository=d['repository'],
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
    def from_dict(cls, d, metadata=Metadata.from_env()):
        is_pipeline_build = metadata.build_pipeline_name and metadata.build_job_name

        if is_pipeline_build:
            default_description = f'{metadata.build_pipeline_name}/{metadata.build_job_name}'
        else:
            default_description = f'ad hoc build #{metadata.build_id}'

        if description_path := d.get('description_path'):
            description = Path(description_path).read_text()
        else:
            description = d.get('descripion', default_description)

        default_target_url = f'{metadata.atc_external_url}'
        if is_pipeline_build:
            default_target_url += (f'/teams/{metadata.build_team_name}'
                                   f'/pipelines/{metadata.build_pipeline_name}'
                                   f'/jobs/{metadata.build_job_name}')
        default_target_url += f'/builds/{metadata.build_id}'

        return cls(
            commit=get_commit_sha(d['commit']),
            state=d['state'],
            description=description,
            target_url=d.get('target_url', default_target_url),
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

    def set_status(self, commit_sha, state, description, target_url):
        url = f'{self.endpoint}/repos/{self.owner}/{self.repository}/statuses/{commit_sha}'
        json_data = {
            'state': state,
            'target_url': target_url
        }
        if description:
            json_data['description'] = description
        resp = self.post(url, json=json_data)
        resp.raise_for_status()
        return resp


@dataclass
class Output:
    version: str
    sha: str
    state: str
    status_id: str

    def serialize(self):
        return {
            'version': {'ref': self.version},
            'metadata': [
                {'name': 'sha', 'value': self.sha},
                {'name': 'state', 'value': self.state},
                {'name': 'status_id', 'value': self.status_id},
            ],
        }


def get_commit_sha(sha_or_repo):
    path = Path(sha_or_repo)
    if path.is_dir():
        return path.joinpath('.git', 'HEAD').read_text().strip()
    elif path.is_file():
        return path.read_text().strip()
    else:
        return sha_or_repo


def ref():
    return int(time.time() // 120)


def show_env():
    eprint = fn.partial(print, file=sys.stderr)
    if sys.stdin.isatty():
        eprint('stdin is a tty')
    else:
        eprint('stdin:', stdin())
    eprint('\ncwd:', os.getcwd())
    eprint('\nargv:', sys.argv)
    eprint('\nenv:', end=' ')
    eprint(pformat(dict(os.environ)))
    try:
        mount_proc = subprocess.run(['mount'], capture_output=True, check=True)
    except Exception:
        eprint('count not run mount')
    else:
        eprint('\nmounts:\n', str(mount_proc.stdout))


def main_in():
    show_env()
    input_data = json.loads(stdin())
    output = {'version': input_data['version'], 'metadata': []}
    json.dump(output, sys.stdout)


def main_out():
    show_env()
    input_data = json.loads(stdin())
    metadata = Metadata.from_env()

    source = Source.from_dict(input_data['source'])
    params = OutParams.from_dict(input_data['params'])

    api = GithubAPI(source.owner, source.repository, source.endpoint)
    resp = api.set_status(params.commit, params.state, params.description,
                          params.target_url)

    # output = Output(
    #     version=input_data['version']['ref'],
    #     sha=params.commit,
    #     state=params.state,
    #     status_id=resp.json()['id'],
    # )
    # json.dump(asdict(output), sys.stdout)

    output = {
        'version': input_data['version'],
        'metadata': [
            {'name': 'sha', 'value': params.commit},
            {'name': 'state', 'value': params.state},
            {'name': 'status_id', 'value': resp.json()['id']},
        ]
    }
    json.dump(output, sys.stdout)


def main_check():
    json.dump([{'ref': str(ref())}], sys.stdout)
