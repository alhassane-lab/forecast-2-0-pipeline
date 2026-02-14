/* Create / update an application user with readWrite on the target DB.
 *
 * This runs only on first container initialization (fresh volume).
 * Env vars are injected via docker-compose.
 */

const appDb = process.env.MONGO_DB || "forecast_2_0";
const appUser = process.env.MONGO_APP_USERNAME;
const appPass = process.env.MONGO_APP_PASSWORD;

if (!appUser || !appPass) {
  print("[initdb] MONGO_APP_USERNAME/MONGO_APP_PASSWORD not set; skipping app user creation");
} else {
  const targetDb = db.getSiblingDB(appDb);
  const roles = [{ role: "readWrite", db: process.env.MONGO_DB }];

  const existing = targetDb.getUser(appUser);
  if (!existing) {
    targetDb.createUser({ user: appUser, pwd: appPass, roles });
    print("[initdb] created app user " + appUser + " with readWrite on " + appDb);
  } else {
    targetDb.updateUser(appUser, { roles });
    print("[initdb] updated app user " + appUser + " roles to readWrite on " + appDb);
  }
}

