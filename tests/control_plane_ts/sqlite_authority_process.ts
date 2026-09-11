import { SqliteAuthorityStore } from "../../loopx/control_plane/coordination/sqlite_authority_store.ts";
import { authorityStoreCommitFixture } from "./authority_store_conformance.ts";

const [directory, operation, revision] = process.argv.slice(2);
const store = new SqliteAuthorityStore(directory!, "goal");
process.stdout.write("ready\n");
for await (const _chunk of process.stdin) {
  const result = await store.commitAuthority(authorityStoreCommitFixture(revision === "null" ? null : revision!, operation!, 1, 1));
  if (operation === "lost-response" && result.status === "applied") process.exit(23);
  process.stdout.write(`${JSON.stringify(result)}\n`);
  break;
}
