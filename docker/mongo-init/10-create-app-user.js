/* Create or update an application user on the target DB.
 *
 * This script is executed by the official MongoDB image entrypoint from
 * /docker-entrypoint-initdb.d during initial database bootstrapping.
 */

const DEFAULT_DB = "forecast_2_0";
const appDb = process.env.MONGO_DB || DEFAULT_DB;
const appUser = process.env.MONGO_APP_USERNAME;
const appPass = process.env.MONGO_APP_PASSWORD;

if (!appUser || !appPass) {
  print("[initdb] missing MONGO_APP_USERNAME or MONGO_APP_PASSWORD; skip app user creation");
} else {
  const targetDb = db.getSiblingDB(appDb);
  const roles = [{ role: "readWrite", db: appDb }];
  const existing = targetDb.getUser(appUser);

  if (!existing) {
    targetDb.createUser({
      user: appUser,
      pwd: appPass,
      roles,
    });
    print("[initdb] created app user '" + appUser + "' on db '" + appDb + "'");
  } else {
    targetDb.updateUser(appUser, {
      pwd: appPass,
      roles,
    });
    print("[initdb] updated app user '" + appUser + "' on db '" + appDb + "'");
  }
}
