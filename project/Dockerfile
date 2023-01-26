# There are 2 reasons for choosing 3.8-slim tag over 3.8:
# 1- it has much lower security risk compared to the latter.
# python:3.8 has        [5 H] [22 M] [242 L]
# python:3.8-slim       [0 H] [0 M]  [47 L]
# where: H: High Severity Issue(s)
#        M: Medium Severity Issue(s)
#        L: Low Severity Issue(s)
# 2- fewer unused packages so lower size and less resource intensive
# Finally I am referencing the image digest to ensure deterministic build
FROM python:3.8-slim@sha256:eda9e0185912dc94bf96d6571e234d12cbd49fc932de1b562bb3217bed755f83

RUN apt-get update && \
    # Ensuring lsof is installed for /metrics endpoint and curl for docker native HEALTHCHECK command
    apt-get install lsof curl -y

# Following least privilege principle, to ensure we don't provide root access to our container default user
RUN groupadd -g 3000 python && \
    useradd -r -u 3000 -g python python

RUN mkdir /usr/app && chown python:python /usr/app
WORKDIR /usr/app

# Making use of docker layer caching by separating the dependencies from the source code
COPY --chown=python:python ./techtrends/requirements.txt .
RUN pip install -r requirements.txt

# Adding source code
COPY --chown=python:python ./techtrends/ .

# su python
USER 3000

EXPOSE 3111

# Initializing database
RUN python init_db.py
ENTRYPOINT [ "python", "app.py" ]
# Adding a healthcheck to TechTrends /healthz endpoint to test the container functionality and this will be ignored by k8s if liveness probe specified
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD curl -f http://localhost:3111/healthz