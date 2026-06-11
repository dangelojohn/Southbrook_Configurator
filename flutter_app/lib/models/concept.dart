// SPDX-License-Identifier: LGPL-3.0-only
//
// One sb.kitchen.design.option as returned by
// /api/v1/kitchen-projects/<id>/concepts.

class Concept {
  final int id;
  final String name;
  final String? description;
  final String? layoutTier;
  final double? estimatedPrice;
  final int? estimatedLeadTimeDays;
  // The contract carries the preview as an attachment id, not a URL. Render
  // it via [imageUrl]; `thumbnailUrl` holds a ready-to-load URL only when the
  // backend supplies one (`preview_url`). See review H1: the /web/image route
  // is session-authenticated, so the clean fix is a `preview_url` field in
  // the contract rather than constructing the attachment URL client-side.
  final int? previewAttachmentId;
  final String? thumbnailUrl;
  final bool isSelected;
  final Map<String, dynamic>? placementData;

  Concept({
    required this.id,
    required this.name,
    this.description,
    this.layoutTier,
    this.estimatedPrice,
    this.estimatedLeadTimeDays,
    this.previewAttachmentId,
    this.thumbnailUrl,
    this.isSelected = false,
    this.placementData,
  });

  factory Concept.fromJson(Map<String, dynamic> json) {
    String? str(dynamic v) => v is String ? v : null;
    int? integer(dynamic v) => v is int ? v : null;
    final price = json['estimated_price'];
    return Concept(
      id: json['id'] as int,
      name: str(json['name']) ?? '',
      // Contract field is `description_html`; tolerate `description` too.
      description: str(json['description_html']) ?? str(json['description']),
      layoutTier: str(json['layout_tier']),
      estimatedPrice: price is num ? price.toDouble() : null,
      estimatedLeadTimeDays: integer(json['estimated_lead_time_days']),
      previewAttachmentId: integer(json['preview_attachment_id']),
      // Prefer an explicit URL if the backend ever provides one.
      thumbnailUrl: str(json['preview_url']) ?? str(json['thumbnail_url']),
      isSelected: json['is_selected'] is bool ? json['is_selected'] as bool : false,
      placementData: json['placement_data'] is Map<String, dynamic>
          ? json['placement_data'] as Map<String, dynamic>
          : null,
    );
  }
}
