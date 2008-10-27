CREATE TABLE IF NOT EXISTS board (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL
    );

CREATE TABLE IF NOT EXISTS forum (
    id INTEGER NOT NULL,
    boardid TEXT NOT NULL,
    title TEXT NOT NULL,
    PRIMARY KEY (id, boardid),
    FOREIGN KEY (boardid) REFERENCES board(id)
    );

CREATE TABLE IF NOT EXISTS message (
    id INTEGER NOT NULL,
    forumid INTEGER NOT NULL,
    boardid TEXT NOT NULL,

    mdate TEXT NOT NULL,
    mtime TEXT NOT NULL,
    mto TEXT NOT NULL,
    mfrom TEXT NOT NULL,
    reference INTEGER,
    subject TEXT NOT NULL,
    body BLOB NOT NULL,

    PRIMARY KEY (id, forumid, boardid),
    FOREIGN KEY (forumid) REFERENCES forum(id),
    FOREIGN KEY (boardid) REFERENCES board(id)
    );
