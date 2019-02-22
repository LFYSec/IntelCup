FROM alpine:latest
COPY mirrors /etc/apk/repositories
RUN apk update
RUN apk add --no-cache postgresql python3 wget python2
VOLUME ["/db","/app"]
RUN adduser -D -h /app -u 1000 -s /bin/sh app
COPY entry.sh /entry.sh
COPY get-pip.py /
RUN python2 get-pip.py
RUN python3 get-pip.py
RUN apk add su-exec
RUN chown postgres:postgres /db
RUN chown app:app /app
RUN chmod +x /entry.sh
COPY pip.conf /etc
RUN apk add build-base python3-dev
RUN pip3 install uvloop tornado asyncpg
RUN pip3 install PyCryptodome
RUN apk add supervisor
COPY supervisor.d /etc/supervisor.d
EXPOSE 8888
EXPOSE 5432
ENTRYPOINT ["/entry.sh"]