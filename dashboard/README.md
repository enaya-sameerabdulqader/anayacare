# gov-violations dashboard (Odoo MCP web app)

Source of the `gov-violations` web app on the Odoo database (React, Arabic RTL).

| File | Web app field |
|---|---|
| `data_code.py` | `mcp.webapp.data_code` (loader: visit log + all violations, objection window computed live) |
| `shared.jsx` | `mcp.webapp.shared_components` (helpers, boxes, tables, the three tabs) |
| `page.jsx` | page `/` `component_code` (header, global filters, tab switch) |
| `styles.css` | `mcp.webapp.shared_styles` |
| `visitors_endpoint.py` | endpoint `visitors` (GET) |

Access: `shared_user_ids` only; the loader returns no data to anyone else.
