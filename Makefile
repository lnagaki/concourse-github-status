IMAGE_REPO := 'registry.barth.tech/library/concourse_github_status'
SOURCE_FILES := $(shell find github_status -type f)

.PHONY: build
build: Dockerfile ${SOURCE_FILES} requirements.txt setup.py
	docker build -t ${IMAGE_REPO}:latest .

.PHONY: push
push: build
	docker push ${IMAGE_REPO}:latest


requirements.txt: setup.py
	pip-compile
