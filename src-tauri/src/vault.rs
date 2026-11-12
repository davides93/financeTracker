use rusqlite::{Connection, OptionalExtension, TransactionBehavior};
use std::sync::Mutex;
use tauri::{Manager, State};
pub struct Vault(pub Mutex<Connection>);
pub fn open(app: &tauri::App) -> Result<Vault, Box<dyn std::error::Error>> {
    let directory = app.path().app_data_dir()?;
    std::fs::create_dir_all(&directory)?;
    #[cfg(unix)] {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&directory, std::fs::Permissions::from_mode(0o700))?;
    }
    let conn = Connection::open(directory.join("vault.sqlite"))?;
    conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS vault (id INTEGER PRIMARY KEY CHECK(id=1), envelope TEXT NOT NULL);")?;
    Ok(Vault(Mutex::new(conn)))
}
#[tauri::command]
pub fn vault_read(state: State<'_, Vault>) -> Result<Option<String>, String> {
    let conn = state.0.lock().map_err(|_| "Archivio occupato")?;
    read(&conn).map_err(|_| "Lettura archivio non riuscita".into())
}
fn read(conn: &Connection) -> rusqlite::Result<Option<String>> {
    conn.query_row("SELECT envelope FROM vault WHERE id=1", [], |row| row.get(0)).optional()
}
fn write(conn: &mut Connection, expected: Option<String>, value: String) -> Result<(), String> {
    if value.len() > 50_000_000 { return Err("Archivio troppo grande".into()); }
    let tx = conn.transaction_with_behavior(TransactionBehavior::Immediate).map_err(|_| "Archivio occupato")?;
    if read(&tx).map_err(|_| "Lettura non riuscita")? != expected { return Err("Archivio modificato. Chiudi e riapri l’app.".into()); }
    tx.execute("INSERT INTO vault (id,envelope) VALUES (1,?1) ON CONFLICT(id) DO UPDATE SET envelope=excluded.envelope", [value]).map_err(|_| "Scrittura non riuscita")?;
    tx.commit().map_err(|_| "Salvataggio non riuscito".into())
}
#[tauri::command]
pub fn vault_write(state: State<'_, Vault>, expected: Option<String>, value: String) -> Result<(), String> {
    let mut conn = state.0.lock().map_err(|_| "Archivio occupato")?;
    write(&mut conn, expected, value)
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_stale_writers_without_overwriting() {
        let mut conn = Connection::open_in_memory().unwrap();
        conn.execute_batch("CREATE TABLE vault (id INTEGER PRIMARY KEY, envelope TEXT NOT NULL)").unwrap();
        write(&mut conn, None, "encrypted-1".into()).unwrap();
        assert!(write(&mut conn, None, "stale".into()).is_err());
        assert_eq!(read(&conn).unwrap().as_deref(), Some("encrypted-1"));
        write(&mut conn, Some("encrypted-1".into()), "encrypted-2".into()).unwrap();
        assert_eq!(read(&conn).unwrap().as_deref(), Some("encrypted-2"));
    }
}
