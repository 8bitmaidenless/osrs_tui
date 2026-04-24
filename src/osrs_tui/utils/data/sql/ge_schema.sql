-- Items the user has bookmarked/tagged for quick lookup
CREATE TABLE IF NOT EXISTS ge_saved_items (
    id          INTEGER PRIMARY KEY,
    item_id     INTEGER NOT NULL UNIQUE,
    item_name   TEXT    NOT NULL,
    note        TEXT,
    tagged_at   TEXT    NOT NULL
);

-- Named price lists (e.g. "Herblore run expenses")
CREATE TABLE IF NOT EXISTS ge_price_lists (
    id          INTEGER PRIMARY KEY,
    list_name   TEXT    NOT NULL,
    list_type   TEXT    NOT NULL CHECK(list_type IN ('expense', 'sale')),
    created_at  TEXT    NOT NULL
);

-- Line items inside a price list
CREATE TABLE IF NOT EXISTS ge_list_items (
    id          INTEGER PRIMARY KEY,
    list_id     INTEGER NOT NULL REFERENCES ge_price_lists(id) ON DELETE CASCADE,
    item_id     INTEGER NOT NULL,
    item_name   TEXT    NOT NULL,
    quantity    INTEGER NOT NULL DEFAULT 1,
    pinned_price INTEGER,
    added_at    TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ge_list_items_list ON ge_list_items(list_id);