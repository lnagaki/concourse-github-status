import os
import re
import sys
import json
import requests
import subprocess
from requests.auth import HTTPBasicAuth
from dataclasses import dataclass
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
            name: os.environ[name.upper()]
            for name, field in cls.__dataclass_params__.items()
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
        description_path = d.get('description_path')
        descption = d.get('descripion') or Path(description_path).read_text()
        default_target_url = f'{metadata.atc_external_url}/builds/{metadata.build_id}'
        return cls(
            commit=d['commit'],
            state=d['state'],
            descption=descption,
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
        url = f'{self.endpoint}/repos/{self.owner}/{self.repo}/statuses/{commit_sha}'
        json_data = {
            'state': state,
            'target_url': target_url
        }
        auth = HTTPBasicAuth(self.owner, self.token)
        resp = self.post(url, json=json_data, auth=auth)
        resp.raise_for_status()
        return resp


def get_commit_sha(sha_or_repo):
    path = Path(sha_or_repo)
    if path.exists():
        proc = subprocess.run(['git', 'rev-parse', 'HEAD'],
                              capture_output=True, cwd=path, check=True)
        return proc.stdout.strip()
    else:
        return sha_or_repo


def main_in():
    print('stdin:', sys.stdin.read())
    print('argv', sys.argv)
    print('env:', os.environ)
    raise NotImplementedError


def main_out():
    input_data = json.load(sys.stdin)
    metadata = Metadata.from_env()

    source = Source.from_dict(input_data['source'])
    params = OutParams.from_dict(input_data['params'])

    api = GithubAPI(source.owner, source.epository, source.endpoint)
    resp = api.set_status(params.commit, params.state, params.descption,
                          params.target_url)
    print(resp.json()['id'])


def main_check():
    raise NotImplementedError
