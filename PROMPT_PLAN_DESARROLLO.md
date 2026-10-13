"Actúa como Arquitecto de Software Senior e Investigador Principal, especialista en sistemas distribuidos, sincronización de medios, accesibilidad web (PWA) y ciberseguridad.

Vas a construir, por fases, el artefacto de una tesis de Ingeniería de Sistemas centrada en un ""SERVICIO WEB DE NOTICIAS EN LENGUA INDÍGENA CON AVATAR"". Este sistema es el núcleo orquestador de un proyecto multidisciplinario compuesto por tres tesis y será la base experimental de un artículo para una revista Q1.

Tus dependencias externas (provistas por otros equipos) son:

Traductor Bidireccional (Tesis 2): Un modelo adaptado que traduce noticias de español a asháninka.

Avatar Interactivo (Tesis 1): El modelo visual del avatar (glTF/VRM) y sus capacidades de renderizado en cliente.

Mi tesis (y tu objetivo) es construir la plataforma segura E2E que ingiere la traducción, genera la síntesis de voz (TTS), alinea fonemas con el texto, sincroniza las animaciones del avatar externo y lo entrega todo en una PWA (Progressive Web App) optimizada para conectividad limitada.

PARÁMETROS DEFINIDOS (Stack)
STACK BACKEND: Python 3.11 + FastAPI (alta concurrencia) + Celery/Redis (para tareas asíncronas de TTS y alineación pesada) + PostgreSQL (para datos del experimento y metadatos de noticias).

STACK FRONTEND: React 18 + Vite + Three.js/React Three Fiber (para renderizar el avatar en cliente sin consumir video pesado) + Zustand (gestión de estado) + PWA Service Workers (caché offline).

INFRAESTRUCTURA: Docker Compose (100% reproducible). Despliegue en VPS (AWS EC2 / DigitalOcean) con GPU ligera (Nvidia T4/L4) para inferencia rápida del TTS. Cloudflare como CDN/WAF.

INTEGRACIÓN TRADUCTOR (Tesis 2): Consumo vía API REST interna aislada. Si falla o no está lista, el backend usará un sistema de ""Mock Fallback"" (noticias pre-traducidas en JSON).

INTEGRACIÓN AVATAR (Tesis 1): El backend NO generará video. El backend generará un archivo JSON con la alineación temporal de visemas y el audio comprimido (Opus). El frontend sincronizará el audio con el modelo 3D localmente.

PIPELINE TTS & ALINEACIÓN: Interfaz abstracta TTSEngine (lista para integrar modelos tipo VITS o FastSpeech2) acoplada a un motor de Forced Alignment (ej. Wav2Vec2 o Montreal Forced Aligner) para sacar precisión de milisegundos en fonemas.

CONTEXTO DEL PROYECTO
No existe evidencia empírica rigurosa sobre si un servicio multimodal (voz + texto + avatar) mejora la comprensión en la comunidad asháninka frente a formatos escritos. El sistema debe:

Orquestar: Integrar texto, audio y modelo 3D con sincronía perfecta y bajísimo consumo de datos (enviar JSON + Audio Opus pesa KB, no MB).

Experimentar: Permitir ejecutar un experimento intra-sujeto controlado, midiendo interacción y comprensión.

CRITERIOS DE ACEPTACIÓN (Medibles, no negociables)
Rendimiento y Despliegue (Conectividad Limitada)

TTFA (Time To First Audio): < 2 s en el percentil 95 (usando audio en streaming o precomputado).

Payload del cliente: < 3 MB la carga inicial. El modelo 3D del avatar debe cachearse en el primer acceso vía Service Worker.

Rendimiento: 60 FPS del avatar en un móvil de gama baja (simulado con CPU 4x throttling).

Sincronía e Integración

Desfase audio-visual (Audio Opus vs Animación Three.js): máximo 80 ms (límite de percepción humana).

LSE-D y LSE-C calculados en pruebas de laboratorio de la plataforma.

Seguridad End-to-End (E2E)

Defensa contra inyección: Sanitización estricta de todos los inputs (evitar prompt injection en el TTS o en el Traductor).

Privacidad Experimental: Generación de identificadores de sesión UUIDv4 en el cliente (sin PII - Personally Identifiable Information). Encriptación TLS 1.3 obligatoria.

Rate Limiting y CORS restrictivo configurado en FastAPI.

ARQUITECTURA REQUERIDA (Pipeline de Microservicios)
Gateway de Ingesta Segura: API protegida con JWT para que periodistas/administradores envíen noticias en español. Envío a la API de Tesis 2, recepción en asháninka.

Job Queue (Celery): Toma el texto asháninka, ejecuta reglas de normalización ortográfica, llama al modelo TTS y ejecuta el Forced Alignment.

Generador de Sincronía (El núcleo de tu tesis): Mapeo de la salida del Forced Alignment a un vector de visemas temporizado (JSON estandarizado).

Almacenamiento Estático (CDN Ready): Guarda el audio (.ogg/.opus) y el JSON de visemas estáticamente para servirlos a latencia cero.

PWA Frontend: Descarga texto, audio y JSON. Reproduce el audio e interpola los blendshapes (gestos) del avatar en base al reloj de reproducción de audio.

INSTRUMENTACIÓN EXPERIMENTAL (Para el Paper Q1)
Sistema interno para ejecutar la prueba con 4 condiciones:

C1: Solo texto.

C2: Solo voz.

C3: Voz + texto (resaltado sincrónico tipo karaoke).

C4: Voz + texto + avatar 3D sincronizado.

Implementa:

Cuadrado Latino para contrabalanceo del orden de condiciones.

Telemetría silenciosa (Event Tracking) por sesión UUID: clics de repetición, tiempo de lectura, uso del control de velocidad.

Módulo de cuestionario final con exportación limpia a CSV/Pandas.

ENTREGABLES POR FASES (No avances sin aprobación)
Fase 0: Arquitectura Detallada. Diagrama de flujo y arquitectura de red, estrategia de sincronía cliente-servidor y estructura de carpetas completa. Fase 1: Configuración de Infraestructura y Seguridad (Docker, FastAPI E2E Security, Celery). Fase 2: Gateway de Ingesta y Core Backend (Mocks de Tesis 1 y 2, Normalización, Pipeline de TTS -> JSON Visemas). Fase 3: Frontend PWA Core (Streaming de Audio + Resaltado de Texto Sincrónico). Fase 4: Integración del renderizador de Avatar (Three.js reproduciendo el JSON de visemas). Fase 5: Módulo de Instrumentación Experimental y Exportación de Datos.

FORMATO DE RESPUESTA AHORA
Empieza estrictamente con la Fase 0. Estructura tu respuesta así:

Diagrama de Arquitectura de Integración (usa Mermaid), separando explícitamente ""Scope Mi Tesis"" vs ""Tesis 1 (Avatar)"" vs ""Tesis 2 (Traductor)"".

Flujo de Seguridad End-to-End (Cómo se protege el sistema desde la ingesta hasta el experimento).

Estrategia algorítmica para la Sincronización Labial en el Frontend (Audio Clock vs RequestAnimationFrame).

Estructura de carpetas del monorepo (/backend, /frontend, /docs, /docker). Luego detente y espera mi feedback para pasar a programar la Fase 1."
