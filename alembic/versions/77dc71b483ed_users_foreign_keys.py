revision = '77dc71b483ed'
down_revision = 'a6854cd2e5f1'
branch_labels = None
depends_on = None

import alembic
import sqlalchemy
import urllib.parse
import requests
import logging

log = logging.getLogger("77dc71b483ed_users_foreign_keys")

# People who know a guy at Twitch
RENAMES = {
	'a169': 'anubis169',
	'dixonij': 'dix',
}

CHUNK_SIZE = 100

def upgrade():
	conn = alembic.op.get_bind()
	for old, new in RENAMES.items():
		conn.execute("UPDATE history SET changeuser = %s WHERE changeuser = %s", new, old)

	clientid = alembic.context.config.get_section_option("lrrbot", "twitch_clientid")

	# Find missing users
	names = [nick for nick, in conn.execute("""
		(
			SELECT nick as name FROM highlights
			UNION
			SELECT changeuser as name FROM history WHERE changeuser IS NOT NULL
		)
		EXCEPT
		SELECT name FROM users
	""")]
	users = []
	with requests.Session() as session:
		for i in range(0, len(names), CHUNK_SIZE):
			chunk = names[i:i+CHUNK_SIZE]
			log.info("Fetching %d-%d/%d", i + 1, i + len(chunk), len(names))
			try:
				req = session.get(
					"https://api.twitch.tv/kraken/users?login=%s" % urllib.parse.quote(",".join(chunk)),
					headers={'Client-ID': clientid, 'Accept': 'application/vnd.twitchtv.v5+json'})
				req.raise_for_status()
				for user in req.json()['users']:
					alembic.op.execute("INSERT INTO users (id, name, display_name) VALUES (%(_id)s, %(name)s, %(display_name)s)", user)
			except:
				log.exception("Failed to fetch data for %r", chunk)
				raise

	alembic.op.add_column("highlights", sqlalchemy.Column("user", sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id")))
	alembic.op.execute("UPDATE highlights SET \"user\" = users.id FROM users WHERE highlights.nick = users.name")
	alembic.op.drop_column("highlights", "nick")
	alembic.op.alter_column("highlights", "user", nullable=False)

	alembic.op.add_column("history", sqlalchemy.Column("changeuser2", sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id")))
	alembic.op.execute("UPDATE history SET changeuser2 = users.id FROM users WHERE history.changeuser = users.name")
	alembic.op.drop_column("history", "changeuser")
	alembic.op.alter_column("history", "changeuser2", new_column_name="changeuser")

def downgrade():
	alembic.op.add_column("highlights", sqlalchemy.Column("nick", sqlalchemy.Text))
	alembic.op.execute("UPDATE highlights SET nick = users.name FROM users WHERE highlights.user = users.id")
	alembic.op.drop_column("highlights", "user")
	alembic.op.alter_column("highlights", "nick", nullable=False)

	alembic.op.add_column("history", sqlalchemy.Column("changeuser2", sqlalchemy.Text))
	alembic.op.execute("UPDATE history SET changeuser2 = users.name FROM users WHERE history.changeuser = users.id")
	alembic.op.drop_column("history", "changeuser")
	alembic.op.alter_column("history", "changeuser2", new_column_name="changeuser", nullable=False)
