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

  factory Project.fromJson(Map<String, dynamic> json) {
    return Project(
      id: json['id'] as int,
      code: json['code'] as String? ?? '',
      name: json['name'] as String? ?? '',
      state: json['state'] as String? ?? 'draft',
      theme: json['theme'] as String?,
      dateTarget: json['date_target'] as String?,
      dateCompleted: json['date_completed'] as String?,
      hasAiAnalysis: json['has_ai_analysis'] as bool? ?? false,
      aiConfirmed: json['ai_confirmed'] as bool? ?? false,
      photoCount: json['photo_count'] as int? ?? 0,
      designOptionCount: json['design_option_count'] as int? ?? 0,
      selectedOptionId: json['selected_option_id'] as int?,
      hasQuote: json['has_quote'] as bool? ?? false,
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
