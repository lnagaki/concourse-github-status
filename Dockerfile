FROM python:3.8-alpine
#FROM python:3.8
ENTRYPOINT ["ash"]
WORKDIR /src
COPY . .
RUN pip install .[dev]
RUN mkdir -p /opt/resource \
  && ln -s /usr/local/bin/in /opt/resource/in \
  && ln -s /usr/local/bin/check /opt/resource/check \
  && ln -s /usr/local/bin/out /opt/resource/out
WORKDIR /opt/resource
