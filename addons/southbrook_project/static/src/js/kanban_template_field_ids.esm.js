/* @odoo-module */

import { patch } from "@web/core/utils/patch";
import { Field } from "@web/views/fields/field";
import { KanbanArchParser } from "@web/views/kanban/kanban_arch_parser";

function nextFieldId(fieldNodes, fieldName) {
    let next = 0;
    for (const fieldId of Object.keys(fieldNodes)) {
        const match = fieldId.match(/_(\d+)$/);
        if (fieldNodes[fieldId].name === fieldName && match) {
            next = Math.max(next, Number(match[1]) + 1);
        }
    }
    return `${fieldName}_${next}`;
}

patch(KanbanArchParser.prototype, {
    parse(xmlDoc, models, modelName) {
        const archInfo = super.parse(...arguments);
        const jsClass = xmlDoc.getAttribute("js_class");

        for (const templateDoc of Object.values(archInfo.templateDocs)) {
            for (const node of templateDoc.querySelectorAll("field:not([field_id])")) {
                const fieldName = node.getAttribute("name");
                if (!fieldName || !models[modelName].fields[fieldName]) {
                    continue;
                }
                if (
                    !node.getAttribute("widget") &&
                    models[modelName].fields[fieldName].type === "many2many"
                ) {
                    node.setAttribute("widget", "many2many_tags");
                }
                const fieldInfo = Field.parseFieldNode(
                    node,
                    models,
                    modelName,
                    "kanban",
                    jsClass
                );
                const fieldId = nextFieldId(archInfo.fieldNodes, fieldName);
                archInfo.fieldNodes[fieldId] = fieldInfo;
                node.setAttribute("field_id", fieldId);
            }
        }
        return archInfo;
    },
});
