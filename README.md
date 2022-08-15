
# Concourse Github Status

A simple [Concourse](http://concourse.ci/)
[resource-type](https://concourse-ci.org/resource-types.html) to interact with
[GitHub build statuses](https://developer.github.com/v3/repos/statuses/).


## Configuration

 * **`owner`** - the owner of the repository

 * **`repository`** - the repository name

 * **`access_token`** - GitHub API access token from a user with write access to
   the repository (minimum token scope of `repo:status`)

 * `branch` - the branch being monitored for new build statuses (only affects
   check) (default: `master`)

 * `context` - a label to differentiate this status from the status of other
   systems (default: `<pipeline-name>/<job-name>`)

 * `endpoint` - GitHub API endpoint (default: `https://api.github.com`)


## Behavior


### `check`

Triggers when the status of the branch for the configured context has been updated.


### `in`

Lookup the state of a status.

Parameters:

 * `commit_ref`: A reference to a commit on a github repository. Can be the name
   of a branch, a tag, or a commit sha. (default: `master`)

 * `output_path`: the file where the fetched status data will be saved. The file
   is in json format. Example output can be found in the "Default response"
   section
   [here](https://docs.github.com/en/rest/reference/repos#get-the-combined-status-for-a-specific-reference--code-samples)
   (default: `githib-build-status.json`)

### `out`

Update the status of a commit. Optionally include a description and target URL
which will be referenced from GitHub.

Parameters:

 * **`commit`** - specific commit sha affiliated with the status. Value must be
   either: path to an input git directory whose `HEAD` will be used; or path to
   an input file whose contents is the sha

 * **`state`** - the state of the status. Must be one of `pending`, `success`,
   `error`, or `failure`

 * `description` - a short description of the status. If one is not provided it
   will be generated from the build pipeline name.

 * `description_path` - path to an input file whose data is the value of `description`

 * `target_url` - the target URL to associate with the status (default:
   concourse build link)


## Example

A typical use case is to update the status of a commit as it traverses your
pipeline. The following example marks the commit as pending before unit tests
start. Once unit tests finish, the status is updated to either success or
failure depending on how the task completes.

```yaml
---
jobs:
  - name: "unit-tests"
    plan:
      - get: "repo"
        trigger: true
      - put: "build-status"
        params: { state: pending, commit: repo }
      - task: "unit-tests"
        file: "repo/ci/unit-tests/task.yml"
        on_failure:
          - put: "build-status"
            params: { state: failure, commit: repo }
      - put: "build-status"
        params: { state: success, commit: repo }

resources:
  - name: "repo"
    type: "git"
    source:
      uri: https://github.com/r-bar/concourse-github-status.git
      branch: master
  - name: "build-status"
    type: "github-status"
    source:
      owner: r-bar
      repository: concourse-github-status
      access_token: {{github_access_token}}

resource_types:
  - name: "github-status"
    type: "docker-image"
    source:
      repository: "registry.barth.tech/library/github-status-resource" # +
      tag: "latest"
```

> Note: If you have several jobs in the pipeline that can fail you can wrap them
> in a [do step](https://concourse-ci.org/jobs.html#schema.step.do-step.do) to
> catch errors or failures from all of them.

## References

 * [Resources (concourse.ci)](https://concourse.ci/resources.html)
 * [Statuses | GitHub Developer Guide (developer.github.com)](https://developer.github.com/v3/repos/statuses/)
 * [Enabling required status checks (help.github.com)](https://help.github.com/articles/enabling-required-status-checks/)
 * [Personal Access Tokens (github.com)](https://github.com/settings/tokens)


## License

[MIT License](./LICENSE)
