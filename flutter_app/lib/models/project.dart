// SPDX-License-Identifier: LGPL-3.0-only
//
// Typed view of the sb.kitchen.project envelope returned by
// /api/v1/kitchen-projects and /api/v1/kitchen-projects/<id>.
// Defensive parsing — missing optional fields tolerate nulls so a
// minor backend addition doesn't crash the client.

class Project {
  final int id;
  final String code;
  final String name;
  final String state;
  final String? theme;
  final String? dateTarget;
  final String? dateCompleted;
  final bool hasAiAnalysis;
  final bool aiConfirmed;
  final int photoCount;
  final int designOptionCount;
  final int? selectedOptionId;
  final bool hasQuote;

  Project({
    required this.id,
    required this.code,
    required this.name,
    required this.state,
    this.theme,
    this.dateTarget,
    this.dateCompleted,
    this.hasAiAnalysis = false,
    this.aiConfirmed = false,
    this.photoCount = 0,
    this.designOptionCount = 0,
    this.selectedOptionId,
    this.hasQuote = false,
  });

  // Odoo serializes empty Char/Date/Many2one fields as `false`, not null, so
  // every optional field is coerced by *type* — a raw `as String?` cast would
  // throw on a `false` value. Keys match the 'southbrook.flutter.api.v1'
  // contract; the list endpoint (_project_summary) and the detail endpoint
  // (_project_detail) carry different shapes, so counts read either an
  // explicit count or the length of an id list.
  factory Project.fromJson(Map<String, dynamic> json) {
    String? str(dynamic v) => v is String ? v : null;
    int? integer(dynamic v) => v is int ? v : null;
    bool flag(dynamic v) => v is bool ? v : false;
    int count(String countKey, String idsKey) {
      final c = json[countKey];
      if (c is int) return c;
      final ids = json[idsKey];
      return ids is List ? ids.length : 0;
    }

    return Project(
      id: json['id'] as int,
      code: str(json['code']) ?? '',
      name: str(json['name']) ?? '',
      state: str(json['state']) ?? 'draft',
      theme: str(json['theme']),
      dateTarget: str(json['date_target']),
      dateCompleted: str(json['date_completed']),
      hasAiAnalysis: flag(json['ai_ready']),
      aiConfirmed: flag(json['ai_confirmed']),
      photoCount: count('photo_count', 'photo_attachment_ids'),
      designOptionCount: count('concept_count', 'concept_ids'),
      selectedOptionId: integer(json['selected_design_option_id']),
      hasQuote: flag(json['has_quote']),
    );
  }

  String get displayLabel => '$code · $name';

  String get stateLabel {
    switch (state) {
      case 'draft':
        return 'Draft';
      case 'designing':
        return 'Designing';
      case 'awaiting_customer':
        return 'Action needed';
      case 'approved':
        return 'Approved';
      case 'in_production':
        return 'In production';
      case 'done':
        return 'Complete';
      case 'cancelled':
        return 'Cancelled';
      default:
        return state;
    }
  }

  bool get canUploadPhoto =>
      state == 'draft' || state == 'designing';

  bool get canReviewConcepts =>
      state == 'awaiting_customer' && designOptionCount > 0;

  bool get canApprove =>
      state == 'awaiting_customer' &&
      selectedOptionId != null;
}
