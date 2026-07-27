/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class Cabinet3dViewer extends Component {
    static template = "cabinet_3d_viewer.Cabinet3dViewerTemplate";

    setup() {
        this.canvasRef = useRef("canvasContainer");
        this.state = useState({
            width: 24,
            height: 34.5,
            depth: 24,
            material: "undefined",
            countertop: "Black Quartz (High Gloss)",
            isLoading: true,
        });

        onMounted(() => {
            this.initThreeCanvas();
        });

        onWillUnmount(() => {
            if (this.animationFrameId) {
                cancelAnimationFrame(this.animationFrameId);
            }
        });
    }

    initThreeCanvas() {
        const container = this.canvasRef.el;
        if (!container || !window.THREE) {
            console.warn("Three.js not loaded on page. Please ensure Three.js library is loaded.");
            this.state.isLoading = false;
            return;
        }

        const THREE = window.THREE;
        const width = container.clientWidth || 600;
        const height = container.clientHeight || 500;

        // Scene Setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0xf8fafc);

        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        this.camera.position.set(40, 40, 50);

        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        container.appendChild(this.renderer.domElement);

        if (THREE.OrbitControls) {
            this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
            this.controls.enableDamping = true;
        }

        // Add Cabinet Mesh with High-Gloss Black Quartz Top
        this.buildCabinetMesh();

        const animate = () => {
            this.animationFrameId = requestAnimationFrame(animate);
            if (this.controls) this.controls.update();
            this.renderer.render(this.scene, this.camera);
        };
        animate();
        this.state.isLoading = false;
    }

    buildCabinetMesh() {
        const THREE = window.THREE;
        const W = this.state.width;
        const H = this.state.height;
        const D = this.state.depth;

        // Black Quartz Material
        const quartzMat = new THREE.MeshStandardMaterial({
            color: 0x050508,
            roughness: 0.02,
            metalness: 0.1,
        });

        const woodMat = new THREE.MeshStandardMaterial({
            color: 0xb8976c,
            roughness: 0.5,
        });

        // 30mm Black Quartz Countertop
        const topGeo = new THREE.BoxGeometry(W + 1.2, 1.25, D + 1.2);
        const topMesh = new THREE.Mesh(topGeo, quartzMat);
        topMesh.position.set(0, H + 0.625, 0);
        this.scene.add(topMesh);

        // Carcass Box
        const boxGeo = new THREE.BoxGeometry(W, H - 4, D);
        const boxMesh = new THREE.Mesh(boxGeo, woodMat);
        boxMesh.position.set(0, (H - 4) / 2 + 4, 0);
        this.scene.add(boxMesh);

        // Lights
        const light = new THREE.DirectionalLight(0xffffff, 1.2);
        light.position.set(20, 40, 30);
        this.scene.add(light);
        this.scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    }
}

// Register as Odoo v19 Web Client Public Snippet / Component
registry.category("public_components").add("cabinet_3d_viewer", Cabinet3dViewer);
