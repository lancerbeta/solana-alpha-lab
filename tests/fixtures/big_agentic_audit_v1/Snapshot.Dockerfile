FROM smial-baa-v1:local
USER 0:0
COPY source /repo
COPY tracked.tar /tmp/tracked.tar
RUN tar -xf /tmp/tracked.tar -C /repo && rm /tmp/tracked.tar && chown -R 1000:1000 /repo
USER 1000:1000
