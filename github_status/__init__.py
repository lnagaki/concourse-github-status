import os
import re
import sys
import json
import requests
import subprocess
from pprint import pprint
from requests.auth import HTTPBasicAuth
from dataclasses import dataclass, asdict
from pathlib import Path

# BUILD_ID = os.environ['BUILD_ID']
# DEFAULT_TARGET_URL = f'{os.environ["ATC_EXTERNAL_URL"]}/builds/{BUILD_ID}'


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
        description = d.get('descripion', '')
        description_path = d.get('description_path')
        if description_path:
            description += Path(description_path).read_text()
        default_target_url = f'{metadata.atc_external_url}/builds/{metadata.build_id}'
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

    def set_status(self, commit_sha, state, description, target_url):
        url = f'{self.endpoint}/repos/{self.owner}/{self.repository}/statuses/{commit_sha}'
        json_data = {
            'state': state,
            'target_url': target_url
        }
        if description:
            json_data['description'] = description
        auth = HTTPBasicAuth(self.owner, self.token)
        resp = self.post(url, json=json_data, auth=auth)
        resp.raise_for_status()
        return resp


@dataclass
class Output:
    sha: str
    state: str
    status_id: str


def get_commit_sha(sha_or_repo):
    path = Path(sha_or_repo)
    if path.exists():
        proc = subprocess.run(['git', 'rev-parse', 'HEAD'],
                              capture_output=True, cwd=path, check=True)
        return proc.stdout.strip()
    else:
        return sha_or_repo


def main_in():
    if sys.stdin.isatty():
        print('stdin is a tty')
    else:
        print('stdin:', sys.stdin.read())
    print('\nargv:', sys.argv)
    print('\nenv:', end=' ')
    pprint(dict(os.environ))
    mount_proc = subprocess.run(['mount'], capture_output=True, check=True)
    print('\nmounts:\n', str(mount_proc.stdout))
    raise NotImplementedError


def main_out():
    input_data = json.load(sys.stdin)
    metadata = Metadata.from_env()

    source = Source.from_dict(input_data['source'])
    params = OutParams.from_dict(input_data['params'])

    api = GithubAPI(source.owner, source.repository, source.endpoint)
    resp = api.set_status(params.commit, params.state, params.description,
                          params.target_url)

    output = Output(
        sha=params.commit,
        state=params.state,
        status_id=resp.json()['id'],
    )
    json.dump(asdict(output), sys.stdout)


def main_check():
    raise NotImplementedError
