import { PGlite } from '@electric-sql/pglite';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const schema = readFileSync(new URL('../database/schema.sql', import.meta.url), 'utf8');
for (const existing of [false, true]) {
  const db = new PGlite();
  await db.exec('CREATE ROLE anon; CREATE ROLE authenticated; CREATE ROLE service_role BYPASSRLS;');
  if (existing) {
    await db.exec(readFileSync(new URL('./fixtures/legacy-schema.sql', import.meta.url), 'utf8'));
    await db.exec("INSERT INTO transactions(user_id,amount,type,category,description,created_at) VALUES (17,25.90,'expense','Transporte','Old row','2026-10-01 01:00:00+00')");
    await db.exec('ALTER TABLE transactions ENABLE ROW LEVEL SECURITY; CREATE POLICY bot_anon_can_read_transactions ON transactions FOR SELECT TO anon USING (user_id IS NOT NULL); GRANT SELECT ON transactions TO anon;');
  }
  await db.exec(schema);
  await db.exec(schema); // safe to rerun
  if (existing) {
    const { rows } = await db.query('SELECT id,amount,occurred_on::text,description FROM transactions');
    assert.equal(rows.length, 1);
    assert.equal(rows[0].occurred_on, '2026-09-30');
    assert.equal(rows[0].description, 'Old row');
  }
  const { rows: access } = await db.query("SELECT has_table_privilege('anon','transactions','SELECT') AS anon_read, has_table_privilege('authenticated','transactions','UPDATE') AS auth_write, has_table_privilege('service_role','transactions','INSERT') AS backend_write");
  assert.equal(access[0].anon_read, false);
  assert.equal(access[0].auth_write, false);
  assert.equal(access[0].backend_write, true);
  await db.exec('SET ROLE service_role');
  const insert = "INSERT INTO transactions(user_id,source_chat_id,source_message_id,amount,type,category,occurred_on) VALUES (17,17,100,50,'expense','Alimentação','2026-10-23') ON CONFLICT(user_id,source_chat_id,source_message_id) DO NOTHING";
  await db.exec(insert);
  await db.exec(insert);
  const { rows: count } = await db.query('SELECT count(*)::int AS n FROM transactions WHERE source_message_id=100');
  assert.equal(count[0].n, 1);
  await db.exec("UPDATE transactions SET deleted_at=now() WHERE source_message_id=100");
  await db.exec(insert);
  assert.equal((await db.query('SELECT count(*)::int AS n FROM transactions WHERE source_message_id=100 AND deleted_at IS NULL')).rows[0].n, 0);
  await assert.rejects(db.exec("INSERT INTO transactions(user_id,amount,type,category) VALUES (17,-1,'expense','Bad')"));
  await db.exec("INSERT INTO finance_drafts VALUES ('00000000-0000-0000-0000-000000000001',17,17,101,'{}',now()+interval '15 minutes')");
  await db.exec('RESET ROLE; SET ROLE anon');
  await assert.rejects(db.query('SELECT * FROM transactions'));
  await assert.rejects(db.query('SELECT * FROM finance_drafts'));
  await db.close();
}
console.log('PASS: clean install, repeated upgrade, record preservation, timezone backfill, grants, duplicate replay, soft delete and positive amounts');
