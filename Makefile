REGISTRY := 'registry.barth.tech/library/concourse_github_status'
DIRTY = $(shell git diff --quiet || echo 'dirty')
GIT_SHORT_SHA = $(shell git rev-parse HEAD --short)
IMAGE_VERSION_TAG = $(shell git describe --all --abbrev=6 --dirty | sed 's#^.*/##')
SOURCE_FILES = $(shell find github_status -type f)


.PHONY: help
help: ## Display this help page
	@echo Commands:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'


.PHONY: build
build: Dockerfile ${SOURCE_FILES} requirements.txt setup.py ## Build the docker image
	docker build -t ${REGISTRY}:latest .


.PHONY: push
push: build ## Push the latest docker image to the registry
	docker tag ${REGISTRY}:latest ${REGISTRY}:${GIT_SHORT_SHA}
	docker tag ${REGISTRY}:latest ${REGISTRY}:${IMAGE_VERSION_TAG}
	docker push ${REGISTRY}:latest
	docker push ${REGISTRY}:${GIT_SHORT_SHA}
	docker push ${REGISTRY}:${IMAGE_VERSION_TAG}


requirements.txt: setup.py
	pip-compile


.PHONY: tag
tag: guard-TAG ## Tag a new version. Requires TAG=x.x.x
	sed -i "s/version=.*/version='${TAG}',/" setup.py
	-git commit setup.py -m 'version: ${TAG}'
	git tag ${TAG}


.PHONY: develop
develop: ## Install the package and its dependencies in development mode
	pip install -e .[dev]


# creates a image tag file for use the the concourse registry resource
.PHONY: ci/tags
ci/tags:
	echo ${GIT_SHORT_SHA} ${IMAGE_VERSION_TAG} | tee $@


# create / update the ci pipeline
.PHONY: set-pipeline
set-pipeline: ci/pipeline.yaml
	fly -t main set-pipeline -c ci/pipeline.yaml -p concourse-github-status


# used to check that a variable is set
guard-%:
	@if [ "${${*}}" = "" ]; then \
		echo "Environment variable $* not set"; \
		exit 1; \
		fi
