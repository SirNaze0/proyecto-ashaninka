// Rol de la interfaz: Ciudadano (público) o Administrador (sala de redacción).
// Elegir «Administrador» NO protege nada por sí solo: la protección real es `require_admin` en el
// backend (cerrado por defecto). Aquí solo se pide el token, se comprueba contra `GET /api/news` y
// se guarda EN MEMORIA (nunca en localStorage ni IndexedDB) mientras la pestaña siga abierta.
export type Role = "ciudadano" | "admin";

export type TokenCheck = "ok" | "rechazado" | "red";

/** Cabecera administrativa (ver backend/app/security.py). */
export const adminHeaders = (token: string): Record<string, string> => ({ "x-admin-token": token });

/** Comprueba el token con una lectura administrativa; no escribe nada en el servidor. */
export async function verificarToken(token: string, fetchFn: typeof fetch = fetch): Promise<TokenCheck> {
  if (!token.trim()) return "rechazado";
  try {
    const r = await fetchFn("/api/news", { headers: adminHeaders(token.trim()) });
    if (r.ok) return "ok";
    return r.status === 403 ? "rechazado" : "red";
  } catch {
    return "red";
  }
}

/** Rutas visibles según el rol: la redacción solo existe para el administrador verificado. */
export function puedeVerRedaccion(role: Role, token: string | null): boolean {
  return role === "admin" && !!token;
}
