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
  final String? thumbnailUrl;
  final bool isSelected;
  final Map<String, dynamic>? placementData;

  Concept({
    required this.id,
    required this.name,
    this.description,
    this.layoutTier,
    this.estimatedPrice,
    this.thumbnailUrl,
    this.isSelected = false,
    this.placementData,
  });

  factory Concept.fromJson(Map<String, dynamic> json) {
    final price = json['estimated_price'];
    return Concept(
      id: json['id'] as int,
      name: json['name'] as String? ?? '',
      description: json['description'] as String?,
      layoutTier: json['layout_tier'] as String?,
      estimatedPrice: price is num ? price.toDouble() : null,
      thumbnailUrl: json['thumbnail_url'] as String?,
      isSelected: json['is_selected'] as bool? ?? false,
      placementData: json['placement_data'] as Map<String, dynamic>?,
    );
  }
}
