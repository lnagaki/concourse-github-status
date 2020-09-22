FROM python:3.8
ENTRYPOINT ["bash"]
WORKDIR /src
COPY . .
RUN mkdir -p /opt/resource
RUN python setup.py install
WORKDIR /opt/resource
RUN ln -s /usr/local/bin/in in \
  && ln -s /usr/local/bin/check check \
  && ln -s /usr/local/bin/out out
