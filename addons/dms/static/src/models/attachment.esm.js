// /** ********************************************************************************
//     Copyright 2024 Subteno - Timothée Vannier (https://www.subteno.com).
//     License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
//  **********************************************************************************/
import {Attachment} from "@mail/core/common/attachment_model";
import {patch} from "@web/core/utils/patch";

patch(Attachment.prototype, {
    get urlRoute() {
        if (this.model_name === "dms.file") {
            return `/web/content/${this.id}`;
        }
        return super.urlRoute;
    },
    get urlQueryParams() {
        if (this.model_name === "dms.file") {
            return {filename: this.name, unique: this.checksum};
        }
        return super.urlQueryParams;
    },
});
