// Punto de entrada mínimo de la opción B (tarea 3.1): TalkingHead. Solo mide el peso del bundle.
import { TalkingHead } from "@met4citizen/talkinghead";

const head = new TalkingHead(document.body, { lipsyncModules: [] });
head.showAvatar({ url: "/models/presentadora.glb", body: "F" });
