#!/bin/sh
export PGDATA=/db
chown postgres /db && chmod 700 /db
mkdir /run/postgresql && chown postgres /run/postgresql
supervisord -c /etc/supervisord.conf
exec /bin/sh