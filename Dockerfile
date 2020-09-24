FROM python:3.8-alpine
#FROM python:3.8
ENTRYPOINT ["ash"]
WORKDIR /src
COPY . .
RUN mkdir -p /opt/resource \
  && ln -s /usr/local/bin/in in \
  && ln -s /usr/local/bin/check check \
  && ln -s /usr/local/bin/out out
RUN pip install .[dev]
WORKDIR /opt/resource
