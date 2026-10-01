-- Additive representation metadata. Evidence and official statuses are untouched.
BEGIN TRANSACTION;
CREATE TABLE korean_knowledge_roles (
 item_id TEXT PRIMARY KEY REFERENCES korean_knowledge_items(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK(role IN ('general','proper_noun','foreign_name','unknown')),
 origin TEXT NOT NULL CHECK(origin IN ('kiwi','manual')),
 metadata TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE korean_knowledge_relations (
 source_item_id TEXT NOT NULL REFERENCES korean_knowledge_items(id) ON DELETE CASCADE,
 target_item_id TEXT NOT NULL REFERENCES korean_knowledge_items(id) ON DELETE CASCADE,
 relation_type TEXT NOT NULL CHECK(relation_type IN ('component_of')),
 metadata TEXT NOT NULL DEFAULT '{}',
 CHECK(source_item_id <> target_item_id),
 PRIMARY KEY(source_item_id,target_item_id,relation_type)
);
CREATE INDEX korean_knowledge_relation_target ON korean_knowledge_relations(target_item_id);
COMMIT;
