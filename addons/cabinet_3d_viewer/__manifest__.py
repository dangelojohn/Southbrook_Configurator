# -*- coding: utf-8 -*-
{
    'name': '3D Cabinet Configurator & Viewer (Odoo v19 CE OWL)',
    'summary': 'Interactive 3D Euro-Standard Cabinet Viewer with High-Gloss Black Quartz Top for Odoo 19 CE Website',
    'description': """
3D Cabinet CAD & Configurator Snippet
======================================
Custom Odoo v19 CE Website Snippet and OWL Component for 3D Cabinet visualization.
- Embedded Three.js WebGL 3D renderer
- Interactive dimensions & high-gloss Black Quartz slab preview
- Full compatibility with Odoo 19 CE Website Builder
- TEST page published at /test (views/test_page.xml)
    """,
    'author': 'Southbrook Cabinetry / CAD Studio',
    'website': 'https://southbrookcabinetry.space',
    'category': 'Website/Website',
    'version': '19.0.1.0.1',
    # southbrook_estimating carries the VENDORED Three.js r160 (air-gapped
    # house doctrine — the zip's CDN three@r128 entries are replaced below;
    # every API this component touches exists on r160).
    'depends': ['website', 'web', 'southbrook_estimating'],
    'data': [
        'views/test_page.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'southbrook_estimating/static/lib/three/three.min.js',
            'southbrook_estimating/static/lib/three/OrbitControls.js',
            'cabinet_3d_viewer/static/src/components/cabinet_3d_viewer.js',
            'cabinet_3d_viewer/static/src/components/cabinet_3d_viewer.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
