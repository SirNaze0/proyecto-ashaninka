// Base IndexedDB única de la PWA ("na-events"). v1 (Fase 4): cola de eventos. v2 (Fase 5): estado
// de la sesión experimental y cola de respuestas de los cuestionarios. La migración solo crea los
// almacenes que faltan, así que una base v1 existente conserva sus eventos pendientes.
export const DB_NAME = "na-events";
export const DB_VERSION = 2;

export const STORE_EVENTS = "events";
export const STORE_EXPERIMENT = "experiment";
export const STORE_RESPONSES = "responses";

export function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_EVENTS)) db.createObjectStore(STORE_EVENTS, { keyPath: "event_id" });
      if (!db.objectStoreNames.contains(STORE_EXPERIMENT)) db.createObjectStore(STORE_EXPERIMENT, { keyPath: "key" });
      if (!db.objectStoreNames.contains(STORE_RESPONSES)) db.createObjectStore(STORE_RESPONSES, { keyPath: "response_id" });
    };
    req.onsuccess = () => {
      const db = req.result;
      db.onversionchange = () => db.close(); // otra pestaña con una versión nueva
      resolve(db);
    };
    req.onerror = () => reject(req.error);
  });
}

/** Una operación en un almacén: devuelve el resultado de la petición al completar la transacción. */
export async function idbTx<T>(
  db: Promise<IDBDatabase>,
  store: string,
  mode: IDBTransactionMode,
  fn: (s: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const d = await db;
  return new Promise((resolve, reject) => {
    const t = d.transaction(store, mode);
    const r = fn(t.objectStore(store));
    t.oncomplete = () => resolve(r.result);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  });
}
