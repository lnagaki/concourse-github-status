import pytest
import json
from io import StringIO
from unittest.mock import Mock, patch


@pytest.fixture
def input_data(mocker):
    def _inner(data):
        stdin = StringIO(json.dumps(data))
        mock = mocker.patch('sys.stdin', stdin)
        return mock
    yield _inner


@pytest.fixture
def api_post(mocker):
    mock = mocker.patch('github_status.GithubAPI.post')

    resp_mock = mocker.Mock()
    resp_mock.json.return_value = {'id': 'testbuildid'}

    mock.return_value = resp_mock

    yield mock


@pytest.fixture
def environ(mocker):
    yield mocker.patch('os.environ', {
        'BUILD_ID': 'MOCK_BUILD_ID',
        'BUILD_NAME': 'MOCK_BUILD_NAME',
        'BUILD_JOB_NAME': 'JOB_NAME',
        'BUILD_PIPELINE_NAME': 'PIPELINE_NAME',
        'BUILD_TEAM_NAME': 'TEAM_NAME',
        'ATC_EXTERNAL_URL': 'https://example.com/some/path',
    })


def test_post_build_status(input_data, environ, api_post, capsys):
    import github_status

    input_data({
        'source': {
            'owner': 'owner',
            'repository': 'my-sweet-project',
        },
        'params': {
            'state': 'success',
            'commit': 'abcd1234'
        }
    })

    github_status.main_out()

    captured = capsys.readouterr()
    api_post.assert_called_once()
    assert api_post.call_args.args[0] == \
        'https://api.github.com/repos/owner/my-sweet-project/statuses/abcd1234'
    assert api_post.call_args.kwargs['auth']
    json_data = api_post.call_args.kwargs['json']
    assert json_data['state'] == 'success'
    out_data = json.loads(captured.out)
    assert out_data['status_id']
    assert out_data['state']
    assert out_data['sha']

