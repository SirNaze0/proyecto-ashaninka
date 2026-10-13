// Punto de entrada mínimo de la opción A (tarea 3.1): three + @pixiv/three-vrm.
// Solo existe para medir el peso del bundle; no es código de producción.
import { VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";
import { PerspectiveCamera, Scene, WebGLRenderer } from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

const renderer = new WebGLRenderer({ antialias: true });
const scene = new Scene();
const camera = new PerspectiveCamera(30, 1, 0.1, 20);
const loader = new GLTFLoader();
loader.register((p) => new VRMLoaderPlugin(p));
loader.load("/models/presentadora.vrm", (gltf) => {
  VRMUtils.removeUnnecessaryVertices(gltf.scene);
  scene.add(gltf.scene);
  renderer.render(scene, camera);
});
