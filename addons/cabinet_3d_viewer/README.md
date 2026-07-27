# Installing 3D Cabinet Configurator in Odoo v19 CE Website

## Directory Structure
Place these exported files into your custom addons directory on your local Odoo v19 server:

```text
custom_addons/
└── cabinet_3d_viewer/
    ├── __manifest__.py
    └── static/
        └── src/
            └── components/
                ├── cabinet_3d_viewer.js
                └── cabinet_3d_viewer.xml
```

## Step-by-Step Odoo 19 CE Local Website Setup

1. **Copy Module Files**:
   Copy the `cabinet_3d_viewer` folder into your Odoo custom addons path (e.g. `/var/lib/odoo/custom_addons/` or your local development directory).

2. **Update App List in Odoo 19**:
   - Log into your Odoo v19 CE Instance (`https://southbrookcabinetry.space` or local `localhost:8069`).
   - Enable **Developer Mode** under Settings.
   - Go to **Apps** -> Click **Update Apps List**.

3. **Install Module**:
   - Search for `3D Cabinet Configurator & Viewer` in Apps and click **Activate**.

4. **Add to Website Page**:
   - Go to your Odoo **Website Builder**.
   - Edit any page or product page.
   - Drag and drop the **3D Cabinet Viewer Snippet** onto your page canvas.
   - Click **Save**!
